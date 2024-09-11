import openai
import config

class OpenAIClient:
    def __init__(self, engine):
        self.engine = engine

    def compare_texts(self, input_text, system_message):

        try:
            response = openai.ChatCompletion.create(
                engine=self.engine,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": input_text}
                ],
                max_tokens=3000
            )
            comparison_result = response['choices'][0]['message']['content']
            return comparison_result
        except Exception as e:
            config.app_logger.error(f"Error comparing summaries: {str(e)}")
            return "Error comparing summaries."