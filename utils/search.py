from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import config


class Search:
    def __init__(self):
        self.search_client = SearchClient(
            endpoint=config.COGNITIVE_SEARCH_CONFIG["endpoint"],
            index_name=config.COGNITIVE_SEARCH_CONFIG["index_name"],
            credential=AzureKeyCredential(config.COGNITIVE_SEARCH_CONFIG["api_key"])
        )

    def find_nearest_neighbors(self, embedding, keyword, top_k=7):
        """
        Finds the nearest neighbors for the given embedding vector, filtered by keyword.

        Args:
            embedding (list): The embedding vector of the new document.
            keyword (str): The keyword to filter the search by.
            top_k (int): The number of nearest neighbors to return (default is 7).

        Returns:
            list: A list of dictionaries containing the nearest neighbors' details.
        """
        try:
            search_results = self.search_client.search(
                search_text="*",
                filter=f"keyword eq '{keyword}'",
                top=top_k,
                include_total_count=True
            )

            neighbors = []
            for result in search_results:
                neighbors.append({
                    "file_path": result["file_path"],
                    "url": result["url"],
                    "website": result["website"],
                    "keyword": result["keyword"],
                    "title": result["title"],
                    "date": result["date"],
                    "summary": result["summary"],
                    "score": result["@search.score"]
                })

            return neighbors

        except Exception as e:
            config.app_logger.error(f"Error finding nearest neighbors: {str(e)}")
            return []