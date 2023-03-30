from flask import Flask, request, jsonify
import requests
import re
import os
import openai
import json

app = Flask(__name__)

openai.api_key = os.environ["OPENAI_API_KEY"]
openai.api_base = ""


def generate_reply(message, is_group):
    # 在这里调用ChatGPT API生成回复，这个示例直接返回原始消息
    # 根据是否为群组消息处理输入文本
    if is_group:
        mention_pattern = r"@\S+\s+"
        input_text = re.sub(mention_pattern, "", message).strip()
    else:
        input_text = message

    parsed_data = json.loads(input_text)
    text_value = parsed_data['text']
    print(f'发送消息：{text_value}')
    # 调用ChatGPT API生成回复
    # 调用自定义 ChatGPT API 生成回复
    headers = {
        "Authorization": f"Bearer {openai.api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": text_value},
        ],
    }

    response = requests.post(
        "https://openapi.braveguozhi.com/v1/chat/completions",
        headers=headers,
        data=json.dumps(data),
    )

    if response.status_code == 200:
        response_data = response.json()
        reply_text = response_data["choices"][0]["message"]["content"].strip()
        return reply_text
    else:
        print(f"Error: {response.text}")
        return "There was an error processing your request."


app_id = os.environ["FEISHU_API_KEY"]
app_secret = os.environ["FEISHU_API_SECRET"]


def gettoken():
    response = requests.post(
        'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/',
        json={
            'app_id': app_id,
            'app_secret': app_secret,
        }
    )

    if response.status_code == 200:
        data = response.json()
        access_token = data.get('tenant_access_token')
        print(f"Access Token: {access_token}")
        return access_token
    else:
        print(f"Error: {response.text}")


@app.route('/feishu_callback', methods=['POST'])
def feishu_callback():
    data = request.json
    event = data.get('event')
    # 处理 challenge 请求
    challenge = data.get('challenge')
    if challenge:
        return jsonify({'challenge': challenge})

    if event is None:
        return jsonify({'code': 1, 'msg': 'Event is missing'})

    # 检查事件类型
    if data['header'].get('event_type') == 'im.message.receive_v1':
        message_content = event['message']['content']
        # 判断消息是否来自群组
        is_group = event['message']['chat_type'] == 'group'
        reply_content = generate_reply(message_content, is_group)
        access_token = gettoken()
        # 发送回复
        print("Sending message:", reply_content)
        # 根据 chat_type 设置回复的目标
        chat_type = event['message']['chat_type']
        if chat_type == 'group':
            target_id = event['message']['chat_id']
            target_key = 'chat_id'
        else:  # 如果是私聊
            target_id = event['sender']['sender_id']['open_id']
            target_key = 'open_id'
        # 发送消息针对飞书
        response = send(target_key, target_id, access_token, reply_content)
        print("Response status:", response.status_code, "Response text:", response.text)
        if response.status_code != 200:
            print(f"Failed to send message, error: {response.text}")
            return jsonify({'code': 1, 'msg': 'Failed to send message'})
    return jsonify({'code': 0, 'msg': 'success'})


def send(target_key, target_id, access_token, reply_content):
    response = requests.post(
        'https://open.feishu.cn/open-apis/message/v4/send/',
        headers={
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {access_token}"
        },
        json={
            target_key: target_id,
            "msg_type": "text",
            "content": {
                "text": reply_content
            }
        }
    )
    return response


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
