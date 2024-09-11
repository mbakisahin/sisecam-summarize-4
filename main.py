import uvicorn
from fastapi import FastAPI, HTTPException
import config
from processors.pipeline import PipelineCoordinator
from utils.system_messages import SYSTEM_MESSAGE_FINAL, SYSTEM_MESSAGE_SUMMARIZATION

def main():
    try:
        config.app_logger.info("Pipeline process started via API.")

        pipeline_coordinator = PipelineCoordinator()
        pipeline_coordinator.run(SYSTEM_MESSAGE_SUMMARIZATION, SYSTEM_MESSAGE_FINAL)

        config.app_logger.info("Pipeline process completed successfully.")
        return {"status": "Pipeline completed successfully."}

    except Exception as e:
        config.app_logger.error(f"Error during pipeline execution: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while running the pipeline.")

if __name__ == "__main__":
    main()
