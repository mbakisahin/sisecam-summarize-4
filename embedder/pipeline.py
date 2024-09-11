import os
import config
from embedder.embedder import Embedder

class EmbeddingPipeline:
    def __init__(self):
        self.embedder = Embedder()

    def process_summary(self, summary_text, file_name, file_url):
        """
        Processes a summary text and returns its embedding.

        Args:
            summary_text (str): The summary text to embed.
            file_name (str): The original file name (e.g., PDF name) associated with the summary.

        Returns:
            dict: A dictionary containing the file name and its embedding.
        """
        try:
            embedding = self.embedder.embed_text(summary_text)
            if embedding:
                embedding_data = {
                    "name": file_name,
                    "url": file_url,
                    "embedding": embedding
                }
                config.app_logger.info(f"Processed summary for file: {file_name}")
                return embedding_data
        except Exception as e:
            config.app_logger.error(f"Error processing summary for file {file_name}: {str(e)}")
            return None
