import json
import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient, SearchIndexingBufferedSender
from uuid import uuid4
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchIndex,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)

import config


class Indexer:
    def __init__(self):
        self.index_client = SearchIndexClient(
            endpoint=config.COGNITIVE_SEARCH_CONFIG["endpoint"],
            credential=AzureKeyCredential(config.COGNITIVE_SEARCH_CONFIG["api_key"])
        )
        self.search_client = SearchClient(
            endpoint=config.COGNITIVE_SEARCH_CONFIG["endpoint"],
            index_name=config.COGNITIVE_SEARCH_CONFIG["index_name"],
            credential=AzureKeyCredential(config.COGNITIVE_SEARCH_CONFIG["api_key"])
        )

    def does_index_exist(self):
        """
        Checks if a specific index exists in the search index client.

        Returns:
            bool: True if the index exists, False otherwise.
        """
        index_names = list(self.index_client.list_index_names())
        return config.COGNITIVE_SEARCH_CONFIG["index_name"] in index_names

    def create_index(self):
        """
        Creates a search index if it does not already exist.

        Returns:
            None
        """
        if not self.does_index_exist():
            try:
                fields = [
                    SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True, sortable=True),
                    SearchableField(name="url", type=SearchFieldDataType.String, searchable=True, filterable=True,
                                    sortable=True),
                    SearchableField(name="file_path", type=SearchFieldDataType.String, searchable=True, filterable=True,
                                    sortable=True),
                    SearchableField(name="website", type=SearchFieldDataType.String, searchable=True, filterable=True,
                                    sortable=True),
                    SearchableField(name="keyword", type=SearchFieldDataType.String, searchable=True, filterable=True,
                                    sortable=True),
                    SearchableField(name="title", type=SearchFieldDataType.String, searchable=True, filterable=True,
                                    sortable=True),
                    SearchableField(name="date", type=SearchFieldDataType.String, filterable=True, sortable=True),
                    SearchableField(name="summary", type=SearchFieldDataType.String, filterable=True, sortable=True),
                    SearchField(
                        name="chunk_vector",
                        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True,
                        vector_search_dimensions=config.EMBEDDING_DIMENSION,
                        vector_search_profile_name="default_vector_search_profile",
                    )
                ]

                search_index = SearchIndex(
                    name=config.COGNITIVE_SEARCH_CONFIG["index_name"],
                    fields=fields,
                    vector_search=VectorSearch(
                        profiles=[
                            VectorSearchProfile(
                                name="default_vector_search_profile",
                                algorithm_configuration_name="default_hnsw_algorithm_config"
                            )
                        ],
                        algorithms=[
                            HnswAlgorithmConfiguration(
                                name="default_hnsw_algorithm_config",
                            )
                        ]
                    )
                )
                self.index_client.create_index(search_index)
                config.app_logger.info("Search Index is created successfully!")
            except Exception as e:
                config.app_logger.error(f"Error creating index: {str(e)}")
        else:
            config.app_logger.info("Index already exists. Skipping index creation.")

    def prepare_document(self, item, final_summary):
        """
        Prepares a document dictionary for indexing.

        Args:
            item (dict): Dictionary containing the file path and embedding.

        Returns:
            dict: Prepared document dictionary ready for indexing.
        """
        try:
            file_path = item['name']
            file_URL = item['url']
            embedding = item['embedding']

            # Boyut kontrolü yapıyoruz
            if len(embedding) != config.EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Embedding dimension mismatch: Expected {config.EMBEDDING_DIMENSION}, got {len(embedding)}")

            parts = file_path.split('/')
            website = parts[0]
            keyword = parts[1]
            file_name = os.path.basename(parts[2])

            date_str = file_name[:10]
            title = file_name[11:].replace('.txt', '')

            document = {
                "id": str(uuid4()),
                "url": file_URL,
                "file_path": file_path,
                "website": website,
                "keyword": keyword,
                "title": title,
                "date": date_str,
                "summary": final_summary,
                "chunk_vector": embedding,
            }
            return document
        except Exception as e:
            config.app_logger.error(f"Error preparing document for {item['name']}: {str(e)}")
            return None

    def ingest_embeddings(self, embeddings, final_summary):
        """
        Ingests embeddings directly into Azure Cognitive Search.

        Args:
            embeddings (list): List of embeddings where each item is a dictionary containing 'name' and 'embedding'.

        Returns:
            None
        """
        self.create_index()

        if not embeddings:
            config.app_logger.error("No embeddings to index.")
            return

        documents = []
        for item in embeddings:
            document = self.prepare_document(item, final_summary)
            if document:
                documents.append(document)

        try:
            self.search_client.upload_documents(documents=documents)
            config.app_logger.info(f"Documents indexed successfully!")
        except Exception as e:
            config.app_logger.error(f"Error during document ingestion: {str(e)}")

    def is_document_indexed(self, file_path):
        """
        Checks if a document with the given file name is already indexed.

        Args:
            file_path (str): The name of the file to check.

        Returns:
            bool: True if the document is indexed, False otherwise.
        """
        try:
            results = self.search_client.search(
                search_text="*",
                filter=f"file_path eq '{file_path}'",
                include_total_count=True
            )
            return results.get_count() > 0
        except Exception as e:
            config.app_logger.error(f"Error checking if document is indexed: {str(e)}")
            return False

