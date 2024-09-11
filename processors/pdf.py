import os
import config

class PDFProcessor:
    """
    A class responsible for processing PDF files, including extracting text,
    removing repetitive patterns, and summarizing the text.
    """

    def __init__(self, text_processor, output_dir="data/summaries"):
        """
        Initializes the PDFProcessor with a TextProcessor and output directory.

        :param text_processor: An instance of the TextProcessor class.
        :param output_dir: The directory where summaries will be saved (default: "data/summaries").
        """
        self.text_processor = text_processor
        self.output_dir = output_dir
        config.app_logger.info("PDFProcessor initialized.")

    def process_pdfs(self, pdf_path, pdf_data, site_name, keyword, system_message):
        """
        Processes a PDF file by extracting and summarizing its content, then saves the summary.

        :param pdf_path: The path of the PDF file.
        :param pdf_data: The binary content of the PDF file.
        :param site_name: The name of the site from which the PDF originates.
        :param keyword: The keyword associated with the PDF.
        :param system_message: The system message or prompt for summarization.
        :return: The path to the saved summary file.
        """
        config.app_logger.info(f"Processing PDF: {pdf_path}")
        decoded_text = self.text_processor.decode_text(pdf_data)
        summary = self.text_processor.summarize_text(decoded_text, system_message)

        summary_dir = os.path.join(self.output_dir, site_name, keyword)
        os.makedirs(summary_dir, exist_ok=True)

        txt_file_path = os.path.join(summary_dir, os.path.basename(pdf_path).replace(".pdf", ".txt"))
        with open(txt_file_path, "w") as txt_file:
            txt_file.write(summary)

        config.app_logger.info(f"Summary saved to {txt_file_path}")
        return txt_file_path
