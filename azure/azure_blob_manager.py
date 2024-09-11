from azure.storage.blob import BlobServiceClient
from io import BytesIO
import zipfile
import config

class AzureBlobStorageManager:
    """
    A manager class for handling operations related to Azure Blob Storage.
    This includes listing blobs, downloading blobs, uploading blobs, and extracting ZIP files.
    """

    def __init__(self):
        """
        Initializes the AzureBlobStorageManager with the given connection string and container name.

        :param connection_string: The connection string to Azure Blob Storage.
        :param container_name: The name of the Azure Blob Storage container.
        """
        # Get connection string and container name from config
        connection_string = config.BLOB_STORAGE_CONFIG['connection_string']
        container_name = config.BLOB_STORAGE_CONFIG['container_name']

        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.blob_service_client.get_container_client(container_name)
        config.app_logger.info(f"Connected to Azure Blob Storage container: {container_name}")

    def list_blobs(self):
        """
        Lists all blobs in the configured container.

        :return: A list of BlobProperties objects representing the blobs in the container.
        """
        config.app_logger.info("Listing blobs in the container...")
        return self.container_client.list_blobs()

    def download_blob(self, blob_name):
        """
        Downloads a blob from Azure Blob Storage.

        :param blob_name: The name of the blob to download.
        :return: The binary content of the blob.
        """
        config.app_logger.info(f"Downloading blob: {blob_name}")
        blob_client = self.container_client.get_blob_client(blob_name)
        return blob_client.download_blob().readall()

    def upload_blob(self, file_path, blob_name):
        """
        Uploads a file to Azure Blob Storage.

        :param file_path: The local file path of the file to upload.
        :param blob_name: The name of the blob in Azure Blob Storage.
        """
        config.app_logger.info(f"Uploading file: {file_path} to blob: {blob_name}")
        blob_client = self.container_client.get_blob_client(blob_name)
        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        config.app_logger.info(f"Uploaded {file_path} to Azure Blob Storage as {blob_name}")

    def extract_zip(self, zip_data):
        """
        Extracts the contents of a ZIP file.

        :param zip_data: The binary content of the ZIP file.
        :return: A tuple containing a list of filenames and a dictionary with filenames as keys and file contents as values.
        """
        config.app_logger.info("Extracting ZIP file contents...")
        with zipfile.ZipFile(BytesIO(zip_data), "r") as zip_ref:
            file_names = zip_ref.namelist()
            files_content = {name: zip_ref.read(name) for name in zip_ref.namelist()}
        config.app_logger.info(f"Extracted {len(file_names)} files from ZIP archive.")
        return file_names, files_content
