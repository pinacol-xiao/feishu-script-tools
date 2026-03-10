import streamlit as st
import requests
import json
import re
import time

# ================= 配置区域 =================
# 🔴 飞书后台最新的 App ID 和 Secret
APP_ID = st.secrets["FEISHU_APP_ID"]
APP_SECRET = st.secrets["FEISHU_APP_SECRET"]

API_HOST = "https://open.feishu.cn/open-apis"
# ===========================================

# 网页图标配置
st.set_page_config(page_title="剧本拼接工具", page_icon="📄", layout="centered")

class FeishuDriveUploader:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = ""

    def get_tenant_access_token(self):
        url = f"{API_HOST}/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        res = requests.post(url, headers=headers, json={"app_id": self.app_id, "app_secret": self.app_secret})
        self.token = res.json().get("tenant_access_token")

    def upload_txt_file(self, file_name, text_content):
        if not self.token: self.get_tenant_access_token()
        url = f"{API_HOST}/drive/v1/files/upload_all"
        headers = {"Authorization": f"Bearer {self.token}"}
        content_bytes = text_content.encode('utf-8')
        
        files = {
            'file_name': (None, file_name),
            'parent_type': (None, 'explorer'), 
            'parent_node': (None, ''),
            'size': (None, str(len(content_bytes))),
            'file': (file_name, content_bytes, 'text/plain')
        }
        
        res = requests.post(url, headers=headers, files=files).json()
        if res.get("code") != 0:
            raise Exception(f"飞书返回错误: {res}")
            
        file_token = res["data"]["file_token"]
        file_url = f"https://www.feishu.cn/file/{file_token}"
        return file_token, file_url

    def add_user_permission(self, file_token, email):
        url = f"{API_HOST}/drive/v1/permissions/{file_token}/members?type=file"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {"member_type": "email", "member_id": email, "perm": "full_access"}
        requests.post(url, headers=headers, json=payload)


def get_sort_weight(filename):
    if "主题" in filename: return 1
    if "主角小传" in filename: return 2
    if "反派小传" in filename or "对手" in filename: return 3
    if "配角小传" in filename: return 4
    if "三幕大纲" in filename or "核心剧情事件": return 5
    if "细纲" in filename: return 6
    if "shootingscript" in filename.lower():
        match = re.search(r'第(\d+)集', filename)
        ep = int(match.group(1)) if match else 99
        return 100 + ep 
    return 999

# ================= 网页 UI 与核心逻辑 =================
st.title("剧本拼接工具")
st.markdown("将分散的剧本文件自动拼接，并一键导入至飞书。")
st.caption("创作者：@pinacol_xiao")

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        doc_title = st.text_input("生成的文件名", value="英文剧名_名字_日期")
    with col2:
        user_email = st.text_input("接收人的飞书邮箱", value="yourname@bytedance.com")

    uploaded_files = st.file_uploader("上传所有 TXT 剧本文件", accept_multiple_files=True, type=['txt'])

download_container = st.empty()

# 按钮加粗依然保留在代码里
if st.button("**开始拼接**", use_container_width=True, type="primary"):
    if not uploaded_files:
        st.warning("请先上传 TXT 文件！")
    elif not user_email:
        st.warning("请填写接收人的飞书邮箱！")
    else:
        sorted_files = sorted(uploaded_files, key=lambda f: get_sort_weight(f.name))
        merged_text = "# 1. 原创意\n\n## 1.1 创意内容\n\n## 1.2 来源\n\n---\n\n"
        state_shooting_printed = False 
        
        # 👇 修改点 1：补全了清洗词库
        skip_keywords = [
            "质检结果", "通过质检", "经逐一审核", "综合评估", "推荐:", "推荐：", 
            "推荐理由", "质检分析", "修改内容", "问题清单", "修正说明", "发现问题", 
            "结构说明", "方案 1", "方案 2", "方案 3", "方案1", "方案2", "质检理由", 
            "位置 |", "问题描述", "问题类型", "The following table:",
            "质检说明：", "检查结论：", "修改后的完整分集细纲：" 
        ]
        
        resume_keywords = ["Theme", "情绪:", "情绪：", "适用冲突", "主角:", "主角：", "对手:", "对手：", "Act ", "姓名", "分场信息", "Shooting script", "Shooting Script", "人物关系图谱", "角色关系图", "核心事件ID"]

        with st.spinner('正在进行数据清洗与拼接...'):
            for file in sorted_files:
                filename = file.name
                raw_lines = file.getvalue().decode("utf-8").splitlines()
                
                if "主题" in filename: merged_text += "# 2. 主题\n\n"
                elif "主角小传" in filename: merged_text += "# 3. 主角小传\n\n"
                elif "反派小传" in filename or "对手" in filename: merged_text += "# 4. 对手小传\n\n"
                elif "配角小传" in filename: merged_text += "# 5. 配角小传\n\n"
                elif "三幕大纲" in filename or "核心剧情事件": merged_text += "# 6. 三幕表格大纲/核心剧情事件\n\n"
                elif "细纲" in filename: merged_text += "# 7. 单集细纲\n\n"
                elif "shootingscript" in filename.lower():
                    if not state_shooting_printed:
                        merged_text += "# 8. Shooting script\n\n"
                        state_shooting_printed = True
                    match = re.search(r'第(\d+)集', filename)
                    ep_num = match.group(1) if match else "X"
                    merged_text += f"#### EP{ep_num}\n\n"
                else:
                    merged_text += f"# {filename}\n\n"

                lines = []
                skip_mode = False
                for line in raw_lines:
                    raw_str = line.strip()
                    clean_str = re.sub(r'^[*#\-\s\|]+', '', raw_str) 
                    
                    if '★' in clean_str or '✓' in clean_str:
                        skip_mode = True
                        continue
                    if re.match(r'^\d+\.\s*(.*?契合度|.*?符合度|淘汰.*?原因|.*?检查|.*?错误|角色.*?问题|集与集衔接断裂)[：:]?', clean_str):
                        skip_mode = True
                        continue
                    if any(clean_str.startswith(kw) for kw in skip_keywords):
                        skip_mode = True
                        continue
                    if re.match(r'^第\d+集([：:]|\s*\[)\s*(将|在|字数|添加)', clean_str):
                        skip_mode = True
                        continue
                    if skip_mode and re.match(r'^第\d+集\s*\|', clean_str):
                        continue
                    if re.match(r'^(《.*?》)?(三幕大纲|分集细纲|表格大纲|Shooting script).*?[\(（]修正版[\)）]', clean_str):
                        skip_mode = True
                        continue
                        
                    is_resume = False
                    if any(clean_str.startswith(kw) for kw in resume_keywords): is_resume = True
                    if clean_str.startswith("集数 |") or clean_str.startswith("Episode |") or clean_str.startswith("编号/ID |"): is_resume = True
                    if re.match(r'^第\d+集([：:]|\s*\[)', clean_str) and not re.match(r'^第\d+集([：:]|\s*\[)\s*(将|在|字数|添加)', clean_str): is_resume = True
                    if re.match(r'^1\.\s+[A-Za-z\u4e00-\u9fa5]', clean_str): is_resume = True

                    if is_resume: skip_mode = False
                    if not skip_mode: lines.append(line)
                
                merged_text += "\n".join(lines) + "\n\n---\n\n"
        
        st.success("拼接已完成✅") 

        file_name_with_ext = f"{doc_title}.txt"
        with download_container:
            st.download_button(
                label="将拼接结果保存至本地（浏览器默认下载文件夹）⬇️",
                data=merged_text.encode("utf-8"),
                file_name=file_name_with_ext,
                mime="text/plain",
                type="secondary"
            )

        try:
            with st.spinner('正在将文件传输至飞书云盘...'):
                uploader = FeishuDriveUploader(APP_ID, APP_SECRET)
                file_token, file_url = uploader.upload_txt_file(file_name_with_ext, merged_text)
                uploader.add_user_permission(file_token, user_email)
                
            st.markdown("---")
            st.markdown(f"""
            ### 飞书直传成功！
            ### **[点击这里，去飞书云盘查看文件]({file_url})**
            
            打开上方链接后，点击页面顶部的「转为在线文档」 按钮，即可获得排版好的飞书文档
            """)

        except Exception as e:
            st.error(f"上传飞书云盘时出错，请检查 App 权限。报错信息: {e}")