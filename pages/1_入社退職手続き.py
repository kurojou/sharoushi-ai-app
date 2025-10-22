
import streamlit as st
import requests
import json
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
import base64
import pandas as pd
import PyPDF2
import docx
import openpyxl

# --- .envからキーを読み込む手動関数 ---
def load_env_variables():
    env_vars = {}
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"')
        return env_vars
    except FileNotFoundError:
        return None

# --- Secrets/環境変数からのキー読み込み ---
api_key = None
supabase_url = None
supabase_key = None

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
except Exception:
    env_vars = load_env_variables()
    if env_vars:
        api_key = env_vars.get("GEMINI_API_KEY")
        supabase_url = env_vars.get("SUPABASE_URL")
        supabase_key = env_vars.get("SUPABASE_KEY")

if not all([api_key, supabase_url, supabase_key]):
    st.error("必要なキー情報を読み込めませんでした。Secretsまたは.envファイルを確認してください。")
    st.stop()

try:
    supabase: Client = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error(f"データベースへの接続に失敗しました: {e}")
    st.stop()

# --- ページコンテンツ ---
st.header("📄 入社・退職手続き")

# --- 手動入力フォーム ---
with st.form("task_generation_form"):
    st.subheader("従業員の属性")
    procedure_type = st.selectbox("手続き種別", ("選択してください", "入社", "退職"), index=0, key="task_procedure_type")
    employment_type = st.selectbox("雇用形態", ("選択してください", "正社員", "契約社員", "パートタイマー", "その他"), index=0, key="task_employment_type")
    nationality = st.selectbox("国籍", ("選択してください", "日本国籍", "外国籍"), index=0, key="task_nationality")
    has_social_insurance = st.checkbox("社会保険に加入", key="task_has_social_insurance")
    has_employment_insurance = st.checkbox("雇用保険に加入", key="task_has_employment_insurance")
    has_side_job = st.checkbox("兼業・副業あり", key="task_has_side_job")
    submitted = st.form_submit_button("タスクを生成する")

# --- ファイルからの一括手続き ---
st.divider()
st.subheader("📂 ファイルから一括手続き")
st.info("顧客から受け取った従業員情報ファイル（Excel, PDF, Word等）をアップロードすると、AIが内容を自動で読み取り、行政提出用のファイルを作成します。")
uploaded_file = st.file_uploader("ここにファイルをアップロードしてください", type=['xlsx', 'pdf', 'docx', 'txt', 'md', 'png', 'jpeg'], label_visibility="collapsed")
process_file_submitted = st.button("ファイルから情報を抽出する", key="file_process_button")

# --- 手動入力フォームの処理ロジック ---
        if submitted:
            if procedure_type == "選択してください" or employment_type == "選択してください" or nationality == "選択してください":
                st.error("手続き種別、雇用形態、国籍は必ず選択してください。")
            else:
                with st.spinner("AIが処理を実行中です..."):
                    try:
                        # 1. タスク生成
                        st.info("1/2: 手続きタスクを生成中...")
                        task_prompt = f'''あなたは、日本の労働法規と社会保険手続きに精通した、非常に優秀な社会保険労務士です。\n以下の従業員の属性情報に基づき、入社・退職手続きに必要な書類をリストアップしてください。\n\n# 従業員属性\n- 手続き種別： {procedure_type}\n- 雇用形態： {employment_type}\n- 国籍： {nationality}\n- 社会保険： {"加入" if has_social_insurance else "未加入"}\n- 雇用保険： {"加入" if has_employment_insurance else "未加入"}\n- 兼業・副業： {"あり" if has_side_job else "なし"}\n\n# あなたのタスク\nこの従業員に必要な行政手続き書類を、書類名(name), 提出期限(submission_deadline), 提出先(submission_to), 備考(note)をキーとするJSON形式でリストアップしてください。'''
                        payload = {
                            "contents": [{"parts": [{"text": task_prompt}]}],
                            "generationConfig": {"temperature": 0.9, "topK": 1, "topP": 1, "maxOutputTokens": 8192, "stopSequences": []},
                            "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}]
                        }
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"
                        response_tasks = requests.post(url, json=payload, timeout=120)
                        response_tasks.raise_for_status()
                        result_json_tasks = response_tasks.json()
                        raw_text_tasks = result_json_tasks['candidates'][0]['content']['parts'][0]['text']
                        start_index = raw_text_tasks.index('[')
                        end_index = raw_text_tasks.rindex(']')
                        json_text_tasks = raw_text_tasks[start_index:end_index+1]
                        tasks = json.loads(json_text_tasks)
                        st.success("手続きタスクの生成が完了しました。")
                        st.table(tasks)

                        # 2. リスク警告
                        st.info("2/2: 手続き内容のリスクをチェックしています...")
                        risk_check_prompt = f'''あなたは、日本の労働法規と社会保険手続きに精通した、非常に優秀な社会保険労務士です。\n以下の従業員の属性情報と、それに基づいて生成された手続きタスクリストをレビューしてください。\n\n# 従業員属性\n- 手続き種別： {procedure_type}\n- 雇用形態： {employment_type}\n- 国籍： {nationality}\n- 社会保険： {"加入" if has_social_insurance else "未加入"}\n- 雇用保険： {"加入" if has_employment_insurance else "未加入"}\n- 兼業・副業： {"あり" if has_side_job else "なし"}\n\n# 生成されたタスクリスト\n{json.dumps(tasks, indent=2, ensure_ascii=False)}\n\n# あなたのタスク\n上記の情報に、法的な矛盾、手続き上の見落とし、あるいは追加で確認すべき事項（リスク）がないかを確認してください。\nもしリスクや確認事項があれば、以下のJSON形式で、重要度が高い順に3つまでリストアップしてください。リスクがなければ、空のリスト `[]` を返してください。\n\n```json\n[\n  {{\n    "risk_level": "高 or 中 or 低",\n    "description": "具体的なリスクや確認事項の内容"\n  }}\n]\n```'''
                        risk_payload = {"contents": [{"parts": [{"text": risk_check_prompt}]}], "generationConfig": payload["generationConfig"], "safetySettings": payload["safetySettings"]}
                        response_risks = requests.post(url, json=risk_payload, timeout=120)
                        response_risks.raise_for_status()
                        result_json_risks = response_risks.json()
                        raw_text_risks = result_json_risks['candidates'][0]['content']['parts'][0]['text']
                        start_index_risk = raw_text_risks.index('[')
                        end_index_risk = raw_text_risks.rindex(']')
                        json_text_risks = raw_text_risks[start_index_risk:end_index_risk+1]
                        risks = json.loads(json_text_risks)
                        st.success("リスクチェックが完了しました。")
                        if risks:
                            st.subheader("⚠️ リスクと確認事項")
                            st.table(risks)
                        else:
                            st.info("チェックの結果、特に注意すべきリスクは見つかりませんでした。")

                        # 3. データ転記
                        st.subheader("📋 転記用データ")
                        transfer_data_text = f'''- 手続き種別: {procedure_type}\n- 雇用形態: {employment_type}\n- 国籍: {nationality}\n- 社会保険加入: {"はい" if has_social_insurance else "いいえ"}\n- 雇用保険加入: {"はい" if has_employment_insurance else "いいえ"}\n- 兼業・副業: {"あり" if has_side_job else "なし"}'''
                        st.code(transfer_data_text, language="text")

                        # 4. Supabaseへのデータ保存
                        st.info("処理結果をデータベースに保存しています...")
                        try:
                            response_db = supabase.table("onboarding_offboarding_records").insert({
                                "procedure_type": procedure_type,
                                "employment_type": employment_type,
                                "nationality": nationality,
                                "has_social_insurance": has_social_insurance,
                                "has_employment_insurance": has_employment_insurance,
                                "has_side_job": has_side_job,
                                "generated_tasks": tasks,
                                "risk_warnings": risks
                            }).execute()
                            st.success("処理結果をデータベースに保存しました！")
                        except Exception as e:
                            st.error(f"データベースへの保存中にエラーが発生しました: {e}")
                            st.exception(e)

                    except requests.exceptions.HTTPError as http_err:
                        if http_err.response.status_code == 503:
                            st.warning("一時的な問題が発生しました。Google Gemini APIが現在利用できません。数分後に再試行してください。")
                        else:
                            st.error(f"AIによる必要書類の生成中にHTTPエラーが発生しました: {http_err}")
                            st.exception(http_err)
                    except Exception as e:
                        st.error(f"AIによる必要書類の生成中にエラーが発生しました: {e}")
                        st.exception(e)

# --- ファイル一括手続きの処理ロジック ---
if process_file_submitted:
    if uploaded_file is not None:
        # (ここにファイル処理のロジックを後で復元)
        pass
    else:
        st.error("ファイルをアップロードしてください。")
