import requests
from openai import OpenAI


def get_deepseek_result(question):
    client = OpenAI(api_key="sk-0f34f167c3d843f99f560ddf14ffbb8d", base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": question},
        ],
        stream=False
    )

    return response.choices[0].message.content
    # 定义 API 的 URL
    # url = "http://101.6.96.160:30005/v1/chat/completions"
    #
    # # 替换为你的实际 Bearer Token
    # bearer_token = "sk-0f34f167c3d843f99f560ddf14ffbb8d"
    #
    # # 设置请求头
    # headers = {
    #     "Authorization": f"Bearer {bearer_token}",
    #     "Content-Type": "application/json"  # 如果需要发送 JSON 数据
    # }
    #
    # # 可选：定义请求体（如果 API 需要 POST 数据）
    # payload = {
    #     "model": "deepseek-v3:671b",  # deepseek-v3:671b, DeepSeek-R1:671B
    #     "messages": [
    #         {
    #             "role": "user",
    #             "content": question
    #         }
    #     ]
    # }
    #
    # try:
    #     # 或者发送 POST 请求
    #     response = requests.post(url, headers=headers, json=payload)
    #
    #     # 检查响应状态码
    #     if response.status_code == 200:
    #         print("请求成功！")
    #         data = response.json()  # 假设返回的是 JSON 数据
    #         print("响应数据:", data)
    #         return data
    #     else:
    #         print(f"请求失败，状态码: {response.status_code}")
    #         print("错误信息:", response.text)
    #         return None
    #
    # except requests.exceptions.RequestException as e:
    #     print("请求过程中发生错误:", e)


if __name__ == '__main__':
    get_deepseek_result("hello")
