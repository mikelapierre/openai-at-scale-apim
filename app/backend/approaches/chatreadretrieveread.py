import os
from openai import AzureOpenAI
import uuid
from approaches.approach import Approach
import chat_log.cosmosdb_logging as cosmosdb_logging

class ChatReadRetrieveReadApproach(Approach):

    # def __init__(self, chatgpt_deployment: str, gpt_deployment: str, sourcepage_field: str, content_field: str):
    def __init__(self, chatgpt_deployment: str, gpt_deployment: str):
        self.chatgpt_deployment = chatgpt_deployment
        self.gpt_deployment = gpt_deployment

    def run(self, history: list[dict], overrides: dict, sessionConfig: dict, userInfo:dict, incomingHeaders: dict, defaultHeaders: dict) -> any:
        request_uuid=uuid.uuid4()
        print("requestID:",request_uuid,",history:", history)
        print("requestID:",request_uuid,",override:", overrides)
        print("requestID:",request_uuid,",sessionConfig:", sessionConfig)
        print("requestID:",request_uuid,",userInfo:", userInfo)
        top_p = overrides.get("top") or 0.95
        temperature = overrides.get("temperature") or 0.7
        max_tokens = overrides.get("maxResponse") or 800
        promptSystemTemplate = overrides.get("prompt_system_template") or "You are an AI assistant that helps people find information."
        pastMessages = sessionConfig.get("pastMessages") or 10
        user_name= userInfo.get("username") or "anonymous user_name"
        user_id = userInfo.get("email") or "anonymous user_id"
        chat_session_id = incomingHeaders.get("Sessionid") or "anonymous-" + str(uuid.uuid4())
        print("user:", {"name": user_name,"user_id":user_id} ) # For Azure Log Analytics
        print("parameters:", {"Max Response": max_tokens, "Temperature": temperature, "Top P": top_p, "Past message included": pastMessages})

        # Step
        system_prompt_template = {}
        system_prompt_template["role"] = "system"
        system_prompt_template["content"] = promptSystemTemplate
        print("prompt:",[system_prompt_template]+self.get_chat_history_as_text(history, pastMessages)) # For Azure Log Analytics

        client = AzureOpenAI(default_headers=defaultHeaders, max_retries=0)
        raw = client.chat.completions.with_raw_response.create(
            messages = [system_prompt_template]+self.get_chat_history_as_text(history, pastMessages),
            model=os.environ.get("AZURE_OPENAI_CHATGPT_DEPLOYMENT"),
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=0,
            presence_penalty=0,                        
            stop=None)
        completion = raw.parse()
        print("completion: ", completion) # For Azure Log Analytics
        print("reponse headers: ", raw.headers)

        document_definition = { "id": str(uuid.uuid4()),
                                "chat_session_id": chat_session_id, 
                                "user": {"name": user_name,"user_id":user_id}, 
                                'message': {"id":completion.id or "anonymous-id",
                                        "prompt":[system_prompt_template]+self.get_chat_history_as_text(history, pastMessages),
                                        "other_attr":[{"completion": completion}],
                                        "previous_message_id":"previous_message_id"}}
        
        #cosmosdb_logging.insert_chat_log(document_definition) # Store prompt log data into Azure Cosmos DB
        return {"answer": completion.choices[0].message.content, "completion": str(completion), "headers": raw.headers }
    

    def get_chat_history_as_text(self, history, pastMessages) -> list:
        history_text = []
        for h in history:
            user_text = {}
            user_text["role"] = "user"
            user_text["content"] = h["user"]

            if h.get("bot") is None:
                history_text = history_text + [user_text]
            else:
                bot_text = {}
                bot_text["role"] = "assistant"
                bot_text["content"] = h.get("bot")
                history_text = history_text + [user_text, bot_text]
        return history_text[-(pastMessages+1):]
