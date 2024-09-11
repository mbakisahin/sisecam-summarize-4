import azure.functions as func
import logging
import pdfplumber
import zipfile
import tempfile
import json
import io
import smtplib
from email.message import EmailMessage
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from uuid import uuid4
from openai import AzureOpenAI
import openai
from azure.core.credentials import AzureKeyCredential
from azure.storage.blob import BlobServiceClient


GPT_CONFIG = {
    'api_key': os.environ['OPENAI_API_KEY'],
    'api_base': os.environ['OPENAI_API_BASE'],
    'api_version': os.environ['GPT_API_VERSION'],
    'model': os.environ['GPT_MODEL'],
    'deployment_name': os.environ['GPT_DEPLOYMENT_NAME']
}

SYSTEM_MESSAGE_GENERAL = """
"""

CONTAINER_NAME = "dummy"


def parse_pdf(pdf_filepath):
    pdf_dict = {}
    with pdfplumber.open(pdf_filepath) as pdf:
        pdf_dict["title"] = pdf.metadata.get("Title", "Title Not Found")
        pdf_dict["page_count"] = len(pdf.pages)
        page_contents = []
        full_content = ""
        for page in pdf.pages:
            page_contents.append(page.extract_text())
            full_content += page.extract_text()
        pdf_dict["full_content"] = full_content
        pdf_dict["page_contents"] = page_contents
    return pdf_dict


def split_pdf_to_chunks(pdf_dict):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=25, length_function=len)
    chunks = []
    for page in pdf_dict["page_contents"]:
        text_chunks = text_splitter.split_text(page)
        for chunk in text_chunks:
            chunks.append({
                "id": str(uuid4()),
                "title": pdf_dict["title"],
                "page_number": pdf_dict["page_contents"].index(page) + 1,
                "total_page_count": pdf_dict["page_count"],
                "chunk": chunk
            })
    return chunks


def split_txt_to_chunks(txt):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=25, length_function=len)
    text_chunks = text_splitter.split_text(txt)
    return text_chunks


def summarize_chunk(chunk):
    prompt = f"""
    You are a helpful assistant designed to comprehend texts given in different languages, get the important 
    information in those texts and summarize them in English.
    
    Instructions:
    - You are not allowed to output a summary that has the same length as the original text. You must summarize the 
    provided text wisely and concisely.
    - You may face with texts that have typos and misspellings as they are extracted using OCR systems which can cause 
    some of these typos. If there is some, try to generate the summary based on the correct version of the text.
    - You are not allowed to output trash summary, even if the provided text is trash (not understandable). 
    - Once again the text may be in different language, so you must figure out the important points and then give them 
    in a concise summary in English, only English. 
    - In general the texts are taken from different parts of regulation documents and you must summarize them in English.
    
    Text:
    ```
    {chunk}
    ```
    """
    response = get_completion(prompt)
    return response


def summarize_json(json_content):
    prompt = f"""
    You are a helpful assistant designed to comprehend tables given in different languages in JSON format, get the important 
    information in those JSON objects and summarize them in English.
    
    Instructions:
    - You are not allowed to output a summary that has the same length as the original text. You must summarize the 
    provided table wisely and concisely.
    - You may face with texts that have typos and misspellings as they are extracted using OCR systems which can cause 
    some of these typos. If there are some, try to generate the summary based on the correct version of the text.
    - You are not allowed to output trash summary, even if the provided text is trash (not understandable). 
    - Once again the table may be in different language, so you must figure out the important points and then give them 
    in a concise summary in English, only English. 
    - In general the tables are taken from different parts of regulation documents and stored as JSON Objects and you must summarize them in English.
    
    Tables:
    ```
    {json_content}
    ```
    """
    response = get_completion(prompt)
    return response


def combine_summaries(summaries):
    prompt = f"""
    You are a helpful assistant designed to combine the given summaries into one consistent summary. You will be 
    provided with summaries of different pieces of one regulation, and you must summarize the points in these 
    summaries to generate the final summary of the whole regulation document.

    Instructions:
    - You are not allowed to output a summary that has the same length as the original text. You must summarize the 
    provided text wisely and concisely.
    - You must figure out the important points and then give them in a concise summary in English, only in English. 

    Summaries:
    ```
    """

    for summary in summaries:
        prompt += f"- {summary}\n\n"

    prompt += f"""
    ```
    """
    response = get_completion(prompt)
    return response


def get_completion(prompt, temperature=0.7, max_tokens=1024, top_p=0.95, frequency_penalty=0, presence_penalty=0,
                   verbose_token=False, system_message=SYSTEM_MESSAGE_GENERAL):
    """
    Get text completion using OpenAI old_api based on the provided prompt.

    Args:
        prompt (str): The input text prompt.
        temperature (float): Controls randomness of the output. Higher values make it more randomized.
        max_tokens (int): Maximum number of tokens in the generated completion.
        top_p (float): Controls the diversity of the output. Lower values make it more focused.
        frequency_penalty (float): Controls relative frequency of tokens. Higher values make it choose rarer tokens.
        presence_penalty (float): Controls repetition of tokens. Higher values make it more focused.
        verbose_token (bool): If True, prints token usage information.
        system_message (str): The system message to be used in the prompt.

    Returns:
        str or None: Generated completion text if successful, else None.
    """
    openai_client = AzureOpenAI(
        api_key=GPT_CONFIG["api_key"],
        api_version=GPT_CONFIG["api_version"],
        azure_endpoint=GPT_CONFIG["api_base"],
        azure_deployment=GPT_CONFIG["deployment_name"],
    )
    try:
        response = openai_client.chat.completions.create(
            model=GPT_CONFIG["model"],
            messages=[
                # {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
        )
        if verbose_token:
            logging.info(f"(OpenAI/GPT Token Usage): Prompt: {response.usage.prompt_tokens} + Completion: "
                         f"{response.usage.completion_tokens} = Total: {response.usage.total_tokens}")
        return response.choices[0].message.content
    except openai.APIConnectionError as e:
        openai_client.close()
        logging.info(f"(OpenAI/GPT): Failed to connect to OpenAI old_api: {e}")
        return None
    except openai.APIError as e:
        openai_client.close()
        logging.info(f"(OpenAI/GPT): OpenAI old_api returned an old_api Error: {e}")
        return None
    except openai.RateLimitError as e:
        openai_client.close()
        logging.info(f"(OpenAI/GPT): OpenAI old_api request exceeded rate limit: {e}")
        return None


def summarize_pdf_file(pdf_filepath):
    pdf_dict = parse_pdf(pdf_filepath)
    logging.info("INFO: PDF Parsed")
    if len(pdf_dict.get("full_content")) > 4:
        pdf_chunks = split_pdf_to_chunks(pdf_dict)
        logging.info("INFO: PDF Splitted to {} Chunks".format(len(pdf_chunks)))
        if len(pdf_chunks) > 1:
            for chunk in pdf_chunks:
                chunk["chunk_summary"] = summarize_chunk(chunk["chunk"])
                logging.info("INFO: {}. Chunk Summarized".format(pdf_chunks.index(chunk) + 1))
            logging.info("INFO: PDF Chunks Summarized")
            summaries = [chunk["chunk_summary"] for chunk in pdf_chunks]
            combined_summary = combine_summaries(summaries)
            logging.info("INFO: PDF Summaries Combined")
        else:
            combined_summary = summarize_chunk(pdf_chunks[0]["chunk"])
            logging.info("INFO: PDF Chunks Summarized")
            logging.info("INFO: PDF Summaries Combined")
        return combined_summary
    else:
        logging.info("INFO: PDF is Empty")
        return ""


def summarize_txt_file(txt_content):
    txt_chunks = split_txt_to_chunks(txt_content)
    logging.info("INFO: txt File Splitted to {} Chunks".format(len(txt_chunks)))
    if len(txt_chunks) > 1:
        chunk_summaries = []
        for chunk in txt_chunks:
            chunk_summary = summarize_chunk(chunk)
            chunk_summaries.append(chunk_summary)
            logging.info("INFO: {}. Chunk Summarized".format(txt_chunks.index(chunk) + 1))
        logging.info("INFO: txt File Chunks Summarized")
        combined_summary = combine_summaries(chunk_summaries)
        logging.info("INFO: txt File Summaries Combined")
    else:
        combined_summary = summarize_chunk(txt_chunks[0])
        logging.info("INFO: txt File Chunks Summarized")
        logging.info("INFO: txt File Summaries Combined")
    return combined_summary


def summarize_json_file(json_content):
    summary = summarize_json(json_content)
    logging.info("INFO: JSON File Summarized")
    return summary


def generate_email_content(txt_summaries, json_summaries, pdf_summaries):
    txt_summaries = [summary for summary in txt_summaries if len(summary) > 0]
    json_summaries = [summary for summary in json_summaries if len(summary) > 0]
    pdf_summaries = [summary for summary in pdf_summaries if len(summary) > 0]
    txt_summaries_exist = len(txt_summaries) > 0
    json_summaries_exist = len(json_summaries) > 0
    pdf_summaries_exist = len(pdf_summaries) > 0
    num_info = (pdf_summaries_exist + json_summaries_exist + txt_summaries_exist)
    if num_info > 0:
        prompt = f"""
        You are a helpful assistant designed to write an email message that will be sent to our employees to notify them with the new regulation.
        You are provided with {num_info} information:
        {"- the general information about the regulation, notification dates etc." if txt_summaries_exist else ""}
        {"- Summary of the notified documents of the regulation" if pdf_summaries_exist else ""}
        {"- And summary of some tables shown in the notified documents of the regulation" if json_summaries_exist else ""}
        
        Instructions:
        - The email message should start with `to whom it may concern` as we are sending it to our employees that are interested in getting information about recent regulations.
        - The email message is acting as notification to our employees about the new released regulation.
        - You must include the informations that I will provide you with in the email message.
        - The tone of the email message must be formal, it must be kind and informative.
        - The name of the email message sender must be `Şişecam - NTT Data DS Team`
        - Do not ask for comments or feedback.
        - The email message should be written in English, only in English.
        
        """
        if txt_summaries_exist:
            prompt += f"""
        The general information about the regulation:
        ```
            """
            for txt_summary in txt_summaries:
                prompt += f"""
        {txt_summary}\n
                """
            prompt += f"""
        ```
            """
        
        if pdf_summaries_exist:
            prompt += f"""

        The Summary of the notified documents of the regulation:
        ```
            """
            for pdf_summary in pdf_summaries:
                prompt += f"""
        {pdf_summary}\n
                """
            prompt += f"""
        ```
            """
        
        if json_summaries_exist:
            prompt += f"""

        The summary of tables shown in the notified documents of the regulation:
        ```
            """
            for json_summary in json_summaries:
                prompt += f"""
        {json_summary}\n
                """
            prompt += f"""
        ```
            """

        prompt += f"""

        The Email Message:
        """
        response = get_completion(prompt)
        response = response.strip()
        response = response.strip("`")
        response = response.strip()
        return response
    else:
        return None


# def upload_blob_file(file_name, file_path):
#     with BlobServiceClient.from_connection_string(os.environ["sisecamusecase_STORAGE"]) as blob_service_client:
#         container_client = blob_service_client.get_container_client(container=CONTAINER_NAME)
#         with open(file_path, mode="rb") as data:
#             blob_client = container_client.upload_blob(name=f"{file_name}.txt", data=data, overwrite=True)


def send_email(receiver_email, subject, message_body):
    # Set up email parameters
    sender_email = 'armaganfdan@gmail.com'
    sender_password = 'vpff bygs beve dkpy'
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587  # Default SMTP port for TLS

    # Create the email message
    msg = EmailMessage()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.set_content(message_body)

    try:
        # Connect to the SMTP server
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            logging.info("Email sent successfully to %s", receiver_email)
    except Exception as e:
        logging.error("Failed to send email: %s", str(e))

app = func.FunctionApp()

@app.blob_trigger(arg_name="myblob", path="dummy/{website}/{keyword}/{name}.zip", connection="sisecamusecase_STORAGE")

def sisecamblobtrigger2(myblob: func.InputStream):
    logging.info(
        f"Python blob trigger function processed blob"
        f"Name: {myblob.name}"
        f"Blob Size: {myblob.length} bytes"
    )

    path_splits = myblob.name.split('/')
    website_name = myblob.name.split('/')[1]
    keyword = myblob.name.split('/')[2]
    file_name_with_extension = myblob.name.split('/')[-1]
    file_name = file_name_with_extension.split('.')[0]

    txt_summaries = []
    pdf_summaries = []
    json_summaries = []
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "my_compressed_zip.zip")
        with open(zip_path, "wb") as fp:
            fp.write(myblob.read())

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)

                if file_path.endswith('.txt'):
                    with open(file_path, 'r') as f:
                        txt_content = f.read()
                        txt_content = txt_content.strip()
                        logging.info("INFO: txt File Parsed")
                        if len(txt_content) > 4:
                            txt_summary = summarize_txt_file(txt_content)
                            if len(txt_summary) > 4:
                                txt_summaries.append(txt_summary)
                        else:
                            logging.info("INFO: txt File is Empty")

                if file_path.endswith('.json'):
                    with open(file_path, 'r') as f:
                        json_content = json.load(f)
                        logging.info("INFO: JSON File Parsed")
                        if len(str(json_content)) > 4:
                            json_summary = summarize_json_file(json_content)
                            if len(json_summary) > 4:
                                json_summaries.append(json_summary)
                        else:
                            logging.info("INFO: JSON File is Empty")

                if file_path.endswith('.pdf'):
                    pdf_summary = summarize_pdf_file(file_path)
                    if len(pdf_summary) > 4:
                        pdf_summaries.append(pdf_summary)

        email_content = generate_email_content(txt_summaries, json_summaries, pdf_summaries)
        if email_content:
            # email_file_path = os.path.join(temp_dir, "myemail.txt")
            # with open(email_file_path, "w", encoding="utf-8") as file:
            #     file.write(email_content)
            # upload_blob_file(file_name, email_file_path)
            # logging.info("INFO: EMAIL UPLOADED TO BLOB STORAGE")
            send_email('armagan.fidan@bs.nttdata.com', f'A new notification about the keyword {keyword} on the website {website_name}', email_content)
