import openai
import config



class Embedder:
    def __init__(self):
        self._configure_openai()

    def _configure_openai(self):
        """
        Configures OpenAI with the necessary API key and endpoint.
        """
        openai.api_type = "azure"
        openai.api_key = config.ADA_CONFIG["api_key"]
        openai.api_base = config.ADA_CONFIG["api_base"]
        openai.api_version = config.ADA_CONFIG["api_version"]

    def embed_text(self, text):
        """
        Generates an embedding for the input text using the OpenAI API.

        Args:
            text (str): The text to be embedded.

        Returns:
            list: The embedding vector.
        """
        try:
            response = openai.Embedding.create(
                input=text,
                engine=config.ADA_CONFIG["deployment_name"],
            )
            return response['data'][0]['embedding']
        except openai.error.APIConnectionError as e:
            config.app_logger.error(f"Failed to connect to OpenAI API: {e}")
        except openai.error.APIError as e:
            config.app_logger.error(f"OpenAI API returned an error: {e}")
        except openai.error.RateLimitError as e:
            config.app_logger.error(f"OpenAI API rate limit exceeded: {e}")
        return None