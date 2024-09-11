import json


class FileManager:
    @staticmethod
    def read_file(file_path):
        """
        Reads the content of a text file.

        Args:
            file_path (str): Path to the text file.

        Returns:
            str: The content of the file.
        """
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

    @staticmethod
    def save_json(data, output_path):
        """
        Saves data as a JSON file.

        Args:
            data (dict): Data to be saved.
            output_path (str): Path to save the JSON file.
        """
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4)
        print(f"Data saved to {output_path}")