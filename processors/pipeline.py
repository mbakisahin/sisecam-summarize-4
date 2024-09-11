import json
import tempfile
import os
import config
import openai

from processors.text import TextProcessor
from processors.pdf import PDFProcessor
from azure.azure_blob_manager import AzureBlobStorageManager
from embedder.pipeline import EmbeddingPipeline
from utils.indexer import Indexer
from utils.search import Search
from utils.system_messages import SYSTEM_MESSAGE_COMPARISON
from utils.comparator import SummaryComparator


class PipelineCoordinator:
    """
    Coordinates the entire processing pipeline, including downloading, extracting,
    processing, summarizing, and uploading files.
    """

    def __init__(self):
        """
        Initializes the PipelineCoordinator with instances for storage management,
        text processing, PDF processing, embedding pipeline, indexing, and nearest neighbor search.
        """
        self.storage_manager = AzureBlobStorageManager()
        self.text_processor = TextProcessor()
        self.pdf_processor = PDFProcessor(self.text_processor)
        self.embedding_pipeline = EmbeddingPipeline()
        self.indexer = Indexer()
        self.nearest_neighbors_finder = Search()
        self.summary_comparator = SummaryComparator(engine="gpt-4o")
        config.app_logger.info("PipelineCoordinator initialized.")

    def process_pdf(self, blob_name, file_name, file_content, system_message_summarization, system_message_final, metadata_content):
        """
        Processes a single PDF file: decodes text, summarizes it, generates embeddings,
        indexes the document, and finds the 7 nearest neighbors.

        :param blob_name: Full blob name including site and keyword information.
        :param file_name: Name of the PDF file.
        :param file_content: The content of the PDF file.
        :param system_message_summarization: The prompt for chunk summarization.
        :param system_message_final: The prompt for final summarization.
        """
        config.app_logger.info(f"Processing PDF file: {file_name}")

        full_file_name = self._construct_full_file_name(blob_name, file_name)

        if self.indexer.is_document_indexed(full_file_name):
            config.app_logger.info(f"File {full_file_name} is already indexed. Skipping processing.")
            return

        decoded_text = self._decode_pdf_content(file_content)
        chunk_summaries = self._summarize_text_in_chunks(decoded_text, system_message_summarization)
        final_summary = self._finalize_document_summary(chunk_summaries, system_message_final)
        embedding_data = self.embedding_pipeline.process_summary(final_summary, full_file_name, metadata_content["URL"])

        if embedding_data:
            self._find_and_compare_nearest_neighbors(embedding_data, blob_name.split('/')[1],
                                                                         final_summary, full_file_name, metadata_content)
            self.indexer.ingest_embeddings([embedding_data], final_summary)

    def _find_and_compare_nearest_neighbors(self, embedding_data, keyword, final_summary, full_file_name, metadata_content):
        """
        Finds the 7 nearest neighbors and compares their summaries with the current document's summary.

        :param embedding_data: The embedding data of the processed document.
        :param keyword: The keyword to filter the search by.
        :param final_summary: The summary of the newly processed PDF.
        :param full_file_name: The file name of the original document.
        :return: None
        """
        config.app_logger.info("Finding the 7 nearest neighbors.")
        nearest_neighbors = self.nearest_neighbors_finder.find_nearest_neighbors(
            embedding=embedding_data['embedding'],
            keyword=keyword
        )

        # Passing the list of neighbors to the comparator to compare with the final summary
        self.summary_comparator.compare_with_multiple_neighbors(
            original_file_name=full_file_name,
            original_summary=final_summary,
            neighbors=nearest_neighbors,
            metadata=metadata_content
        )

    def process_zip_blob(self, blob, system_message_summarization, system_message_final):
        """
        Processes a ZIP blob by extracting its contents and processing each PDF file.

        :param blob: The BlobProperties object representing the ZIP file in Azure Blob Storage.
        :param system_message_summarization: The prompt for chunk summarization.
        :param system_message_final: The prompt for final summarization.
        """
        config.app_logger.info(f"Processing ZIP blob: {blob.name}")

        file_names, files_content = self._extract_files_from_zip(blob)

        metadata_content = None  # Metadata'yı saklamak için bir değişken

        for file_name in file_names:
            if "metadata_" in file_name:
                metadata_bytes = files_content[file_name]
                try:
                    metadata_content = json.loads(metadata_bytes.decode('utf-8'))  # Bytes'tan JSON'a dönüştürme
                except json.JSONDecodeError:
                    config.app_logger.error(f"Failed to decode metadata file: {file_name}")
                    metadata_content = None

        for file_name in file_names:
            if file_name.endswith(".pdf"):
                self.process_pdf(blob.name, file_name, files_content[file_name], system_message_summarization,
                                 system_message_final, metadata_content)

        config.app_logger.info(f"Finished processing ZIP blob: {blob.name}\n{'-' * 50}")

    def run(self, system_message_summarization, system_message_final):
        """
        Runs the pipeline by processing all ZIP blobs in the Azure Blob Storage container.

        :param system_message_summarization: The prompt for chunk summarization.
        :param system_message_final: The prompt for final summarization.
        """
        config.app_logger.info("PipelineCoordinator running...")

        with tempfile.TemporaryDirectory() as temp_dir:
            blob_list = self.storage_manager.list_blobs()
            i = 1
            for blob in blob_list:
                if i > 1689:
                    if blob.name.endswith(".zip"):
                        self.process_zip_blob(blob, system_message_summarization, system_message_final)
                        print(i)
                        i += 1
                else:
                    i += 1

        config.app_logger.info("PipelineCoordinator run completed.")



    def _construct_full_file_name(self, blob_name, file_name):
        """
        Constructs the full file name including site name and keyword from the blob name.

        :param blob_name: Full blob name including site and keyword information.
        :param file_name: Name of the PDF file.
        :return: Constructed full file name.
        """
        parts = blob_name.split('/')
        site_name = parts[0]
        keyword = parts[1]
        return f"{site_name}/{keyword}/{file_name}"

    def _decode_pdf_content(self, file_content):
        """
        Decodes the content of a PDF file.

        :param file_content: The content of the PDF file.
        :return: Decoded text from the PDF.
        """
        return self.pdf_processor.text_processor.decode_text(file_content)

    def _summarize_text_in_chunks(self, text, system_message):
        """
        Splits text into chunks and summarizes each chunk.

        :param text: The full text of the document.
        :param system_message: The prompt for chunk summarization.
        :return: A list of chunk summaries.
        """
        config.app_logger.info("Splitting text into chunks for summarization.")
        chunks = self.text_processor.split_text_by_tokens(text)
        config.app_logger.info("Summarizing each chunk.")
        return self.text_processor.summarize_chunks(chunks, system_message)

    def _finalize_document_summary(self, chunk_summaries, system_message):
        """
        Combines chunk summaries into a final cohesive summary.

        :param chunk_summaries: A list of summarized chunks.
        :param system_message: The prompt for final summarization.
        :return: A final summary of the entire document.
        """
        config.app_logger.info("Combining chunk summaries into a final summary.")
        combined_summary = self.text_processor.combine_summaries(chunk_summaries)
        return self.text_processor.summarize_text(combined_summary, system_message)

    def _extract_files_from_zip(self, blob):
        """
        Extracts files from a ZIP blob.

        :param blob: The BlobProperties object representing the ZIP file in Azure Blob Storage.
        :return: A tuple containing file names and their contents.
        """
        zip_data = self.storage_manager.download_blob(blob.name)
        return self.storage_manager.extract_zip(zip_data)
