# app/crawler/validation_pipeline.py
import json
import anyio
from app.crawler.excel_reader import stream_excel_records
from app.crawler.csv_reader import stream_csv_records
from app.crawler.excel_writer import write_validated_excel_stream
from app.crawler.validator import prep_rules_from_dict, build_duplicate_index, validate_chunk
from app.core.config import settings
from app.core.logging_utils import get_app_logger
from app.profiler import StepProfiler
from app.services.audit_service import update_progress, update_audit_status
from app.services.rules_service import get_rules_json
from app.services.notification_service import publish
from app.s3_utils import read_file_from_s3, upload_bytes_to_s3, generate_presigned_get_url
from app.models import AuditStatus

CHUNK_SIZE = 5000
WORKERS = 4


async def run_excel_validation_pipeline(app, session, audit_id: str, key_in: str, rules_id):
    """Main async validation flow supporting Excel & CSV, background + inline + WebSocket."""
    logger = get_app_logger()
    profiler = StepProfiler()

    # ---- WebSocket-safe publish helper ----
    async def safe_publish(event: dict):
        """Only publish to WebSocket/Redis if app is available."""
        if app is not None:
            try:
                await publish(app, audit_id, event)
            except Exception as e:
                logger.warning(f"⚠️ Could not publish WebSocket event: {e}")
        else:
            logger.debug(f"(background mode) Skipped publish: {event}")

    try:
        logger.info(f"🏁 Starting validation pipeline (audit_id={audit_id}, key={key_in})")
        await update_audit_status(session, audit_id, AuditStatus.RUNNING)
        profiler.start()

        # ---- Step 1: Read from S3 ----
        file_bytes, content_type = await read_file_from_s3(settings.S3_BUCKET, key_in)
        profiler.step("read_s3")
        logger.info("📦 S3 file loaded")

        # ---- Step 2: Detect Excel / CSV ----
        if "spreadsheetml" in (content_type or ""):
            records_iter = stream_excel_records(file_bytes)
            logger.info("🧾 File type detected: Excel")
        elif "csv" in (content_type or ""):
            records_iter = stream_csv_records(file_bytes.getvalue())
            logger.info("🧾 File type detected: CSV")
        else:
            raise ValueError(f"Unsupported S3 Content-Type: {content_type}")

        records = list(records_iter)
        total_records = len(records)
        logger.info(f"📊 Total records: {total_records}")

        await update_progress(session, audit_id, 0, total_records)
        await safe_publish({"type": "init", "status": "RUNNING", "message": f"Loaded {total_records} records"})

        # ---- Step 3: Load validation rules ----
        rules_cfg = await get_rules_json(session, rules_id)
        if not rules_cfg:
            raise ValueError(f"No rules found for rules_id={rules_id}")

        rules, unique_cols, unique_mode = prep_rules_from_dict(rules_cfg)
        dup_index = build_duplicate_index(records, unique_cols)
        logger.info("⚙️ Validation rules prepared")

        # ---- Step 4: Chunked async validation ----
        chunks = [(i, records[i:i+CHUNK_SIZE]) for i in range(0, total_records, CHUNK_SIZE)]
        validated_records, processed, total_success, total_failure = [], 0, 0, 0

        logger.info(f"🚀 Starting chunked validation: chunks={len(chunks)}, workers={WORKERS}")

        for batch_start in range(0, len(chunks), WORKERS):
            batch = chunks[batch_start: batch_start+WORKERS]
            results = []

            async with anyio.create_task_group() as tg:
                for start_idx, rows in batch:
                    tg.start_soon(_collect_results, results, start_idx, rows, rules, dup_index, unique_cols, unique_mode)

            for start_idx, (chunk_valid, succ, fail) in sorted(results, key=lambda x: x[0]):
                validated_records.extend(chunk_valid)
                processed += len(chunk_valid)
                total_success += succ
                total_failure += fail

                percent = round((processed / total_records) * 100, 2)
                await update_progress(session, audit_id, processed, total_records)
                await safe_publish({"type": "progress", "processed": processed, "percent": percent})

        profiler.step("validate_records")
        logger.info("✔ Validation finished")

        # ---- Step 5: Upload Excel + JSON results ----
        quality = "PASS" if total_failure == 0 else "FAIL"
        base = key_in.split("/")[-1].rsplit(".", 1)[0]
        excel_key = f"{settings.OUTPUT_PREFIX}/{base}_{audit_id}_{quality}.xlsx"
        json_key = f"{settings.OUTPUT_PREFIX}/{base}_{audit_id}_{quality}.json"

        excel_bytes = await write_validated_excel_stream(validated_records)
        await upload_bytes_to_s3(settings.S3_BUCKET, excel_key, excel_bytes.getvalue())
        profiler.step("upload_excel")
        logger.info(f"📤 Excel uploaded: {excel_key}")

        json_bytes = json.dumps(validated_records, indent=2).encode()
        await upload_bytes_to_s3(settings.S3_BUCKET, json_key, json_bytes)
        profiler.step("upload_json")
        logger.info(f"📤 JSON uploaded: {json_key}")

        # ---- Step 6: Final WebSocket broadcast ----
        excel_url = await generate_presigned_get_url(settings.S3_BUCKET, excel_key)
        json_url = await generate_presigned_get_url(settings.S3_BUCKET, json_key)

        await safe_publish({
            "type": "completed",
            "status": "COMPLETED",
            "percent": 100.0,
            "excel_url": excel_url,
            "json_url": json_url,
            "success_count": total_success,
            "failure_count": total_failure
        })

        # ---- Step 7: Update audit record ----
        await update_audit_status(
            session,
            audit_id,
            AuditStatus.COMPLETED,
            total_records=total_records,
            success_count=total_success,
            failure_count=total_failure,
            profiler_data=profiler.result(),
            progress_percent=100.0,
            excel_s3_key=excel_key,
            json_s3_key=json_key,
            rules_id=rules_id,
        )

        logger.info(f"🏁 Pipeline DONE (audit_id={audit_id})")

    except Exception as e:
        logger.exception(f"❌ Pipeline failed: {e}")
        await update_audit_status(session, audit_id, AuditStatus.FAILED, error_message=str(e))
        await safe_publish({"type": "error", "status": "FAILED", "message": str(e)})
        raise


async def _collect_results(acc, start_idx, rows, rules, dup_index, unique_cols, unique_mode):
    """Thread worker for validation."""
    def run_sync():
        return validate_chunk(rows, start_idx+1, rules, dup_index, unique_cols, unique_mode)

    result = await anyio.to_thread.run_sync(run_sync)
    acc.append((start_idx, result))
