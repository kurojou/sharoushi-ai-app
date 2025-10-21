import streamlit as st
import requests
import json
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta

# --- ページ設定 ---
st.set_page_config(
    page_title="OOG: 社労士向けAIアシスタント",
    page_icon="📄",
    layout="wide"
)

# --- JST変換関数 ---
def to_jst(utc_str):
    try:
        utc_dt = datetime.fromisoformat(str(utc_str).replace('Z', '+00:00'))
        jst_tz = timezone(timedelta(hours=9))
        jst_dt = utc_dt.astimezone(jst_tz)
        return jst_dt.strftime('%Y-%m-%d %H:%M')
    except:
        return utc_str

# --- Streamlit アプリケーションの定義 ---
st.title("OOG: 社労士向けAIアシスタント")
st.caption("On/Off Boarding Genius - 入退社手続きと就業規則改定を、AIで劇的に効率化するツール")

# --- Secretsからのキー読み込み（Streamlitの公式手法） ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(supabase_url, supabase_key)
    st.success("APIキーとデータベースの接続を確認しました。")
except Exception as e:
    st.error(f"必要なキー情報が設定されていません。StreamlitのSecretsを確認してください。")
    st.stop()

# --- 履歴表示 機能 ---
with st.expander("📂 過去の実行履歴を表示する"):
    history_col1, history_col2 = st.columns(2)
    with history_col1:
        st.subheader("入社・退職手続き 履歴")
        try:
            onboarding_history = supabase.table("onboarding_offboarding_records").select("created_at, procedure_type, employment_type, nationality").order("created_at", desc=True).limit(5).execute()
            if onboarding_history.data:
                for record in onboarding_history.data:
                    st.markdown(f"**実行日時:** {to_jst(record['created_at'])}")
                    st.markdown(f"- **手続き種別:** {record['procedure_type']} / **雇用形態:** {record['employment_type']} / **国籍:** {record['nationality']}")
                    st.markdown("---")
            else:
                st.info("履歴はまだありません。")
        except Exception as e:
            st.warning(f"履歴の取得中にエラーが発生しました: {e}")

    with history_col2:
        st.subheader("就業規則改正 履歴")
        try:
            rule_history = supabase.table("rule_amendment_records").select("created_at, current_rule").order("created_at", desc=True).limit(5).execute()
            if rule_history.data:
                for record in rule_history.data:
                    st.markdown(f"**実行日時:** {to_jst(record['created_at'])}")
                    with st.expander(f"改正した条文（冒頭）: {record['current_rule'][:20]}..."):
                        st.text(record['current_rule'])
                    st.markdown("---")
            else:
                st.info("履歴はまだありません。")
        except Exception as e:
            st.warning(f"履歴の取得中にエラーが発生しました: {e}")

# --- 機能のメインコンテナ ---
col1, col2 = st.columns(2, gap="large")

with col1:
    with st.container(border=True):
        st.header("📄 入社・退職手続き")
        with st.form("task_generation_form"):
            st.subheader("従業員の属性")
            procedure_type = st.selectbox("手続き種別", ("選択してください", "入社", "退職"), index=0)
            employment_type = st.selectbox("雇用形態", ("選択してください", "正社員", "契約社員", "パートタイマー", "その他"), index=0)
            nationality = st.selectbox("国籍", ("選択してください", "日本国籍", "外国籍"), index=0)
            has_social_insurance = st.checkbox("社会保険に加入")
            has_employment_insurance = st.checkbox("雇用保険に加入")
            has_side_job = st.checkbox("兼業・副業あり")
            submitted = st.form_submit_button("タスクを生成する")

with col2:
    with st.container(border=True):
        st.header("📖 就業規則の改正")
        with st.form("rule_amendment_form"):
            st.subheader("現行の条文と改正の要点")
            current_rule = st.text_area("現行の就業規則の条文", height=150, placeholder="（例）第XX条...")
            law_amendment_points = st.text_area("法改正・ガイドラインの要点", height=150, placeholder="（例）フレックスタイム制の導入...")
            reference_file = st.file_uploader("参考資料（.txt, .md）", type=['txt', 'md'])
            rule_submitted = st.form_submit_button("分析を開始する")

# --- 結果表示ロジック ---
if submitted:
    if procedure_type == "選択してください" or employment_type == "選択してください" or nationality == "選択してください":
        st.error("手続き種別、雇用形態、国籍は必ず選択してください。")
    else:
        with st.spinner("AIが処理を実行中です..."):
            try:
                # 1. タスク生成
                st.info("1/2: 手続きタスクを生成中...")
                task_prompt = f'''従業員の属性は以下の通りです。

- 手続き種別： {procedure_type}
- 雇用形態： {employment_type}
- 国籍： {nationality}
- 社会保険： {"加入" if has_social_insurance else "未加入"}
- 雇用保険： {"加入" if has_employment_insurance else "未加入"}
- 兼業・副業： {"あり" if has_side_job else "なし"}

この従業員に必要な行政手続きを、手続き名(name), 提出期限(submission_deadline), 提出先(submission_to), 備考(note)をキーとするJSON形式でリストアップしてください。'''
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
                risk_check_prompt = f'''あなたは、日本の労働法規と社会保険手続きに精通した、非常に優秀な社会保険労務士です。
以下の従業員の属性情報と、それに基づいて生成された手続きタスクリストをレビューしてください。

# 従業員属性
- 手続き種別： {procedure_type}
- 雇用形態： {employment_type}
- 国籍： {nationality}
- 社会保険： {"加入" if has_social_insurance else "未加入"}
- 雇用保険： {"加入" if has_employment_insurance else "未加入"}
- 兼業・副業： {"あり" if has_side_job else "なし"}

# 生成されたタスクリスト
{json.dumps(tasks, indent=2, ensure_ascii=False)}

# あなたのタスク
上記の情報に、法的な矛盾、手続き上の見落とし、あるいは追加で確認すべき事項（リスク）がないかを確認してください。
もしリスクや確認事項があれば、以下のJSON形式で、重要度が高い順に3つまでリストアップしてください。リスクがなければ、空のリスト `[]` を返してください。

```json
[
  {{
    "risk_level": "高 or 中 or 低",
    "description": "具体的なリスクや確認事項の内容"
  }}
]
```'''
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

                # 3. データベースへの保存
                try:
                    st.info("結果をデータベースに保存しています...")
                    data_to_insert = {
                        "procedure_type": procedure_type,
                        "employment_type": employment_type,
                        "nationality": nationality,
                        "has_social_insurance": has_social_insurance,
                        "has_employment_insurance": has_employment_insurance,
                        "has_side_job": has_side_job,
                        "generated_tasks": json.dumps(tasks),
                        "risk_warnings": json.dumps(risks)
                    }
                    supabase.table("onboarding_offboarding_records").insert(data_to_insert).execute()
                    st.success("データベースへの保存が完了しました。")
                except Exception as db_e:
                    st.error(f"データベースへの保存中にエラーが発生しました: {db_e}")

                # 4. データ転記
                st.subheader("📋 転記用データ")
                transfer_data_text = f'''- 手続き種別: {procedure_type}
- 雇用形態: {employment_type}
- 国籍: {nationality}
- 社会保険加入: {"はい" if has_social_insurance else "いいえ"}
- 雇用保険加入: {"はい" if has_employment_insurance else "いいえ"}
- 兼業・副業: {"あり" if has_side_job else "なし"}'''
                st.code(transfer_data_text, language="text")

            except Exception as e:
                st.error(f"処理中にエラーが発生しました: {e}")

if rule_submitted:
    if not current_rule or not law_amendment_points:
        st.error("現行の条文と、法改正の要点の両方を入力してください。")
    else:
        with st.spinner("AIが処理を実行中です..."):
            try:
                reference_text = ""
                if reference_file is not None:
                    try:
                        reference_text = reference_file.getvalue().decode('utf-8')
                        st.info("参考資料を読み込み、AIへの指示に含めました。")
                    except Exception as e:
                        st.warning(f"参考資料の読み込みに失敗しました: {e}")

                rule_prompt = f'''あなたは、日本の労働法規に精通した、非常に優秀な社会保険労務士です。
以下の「現行の条文」を、「法改正の要点」と、必要であれば「参考資料」に基づいて修正し、新しい条文案を作成してください。
また、その際に企業側が注意すべき法的リスクや実務上の課題も指摘してください。

# 現行の条文
{current_rule}

# 法改正の要点
{law_amendment_points}

# 参考資料
{reference_text}

# あなたのタスク
1. 上記要点を満たす、就業規則の新しい条文のドラフトを作成してください。
2. この規定を導入する際に、企業側が注意すべき法的リスクや実務上の課題を指摘してください。

# 出力形式
必ず以下のJSON形式で出力してください。
```json
{{
  "new_rule_draft": "ここに新しい条文のドラフトを記述",
  "risks_and_issues": [
    {{
      "type": "法的リスク or 実務上の課題",
      "description": "具体的なリスクや課題内容を記述"
    }}
  ]
}}
```'''
                rule_payload = {
                    "contents": [{"parts": [{"text": rule_prompt}]}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192},
                    "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}, {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}]
                }

                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"
                response = requests.post(url, json=rule_payload, timeout=180)
                response.raise_for_status()
                result_json = response.json()
                raw_text = result_json['candidates'][0]['content']['parts'][0]['text']

                try:
                    start_index = raw_text.index('{')
                    end_index = raw_text.rindex('}')
                    json_text = raw_text[start_index:end_index+1]
                    data = json.loads(json_text)
                    st.success("分析が完了しました。")
                    st.subheader("新しい条文案")
                    st.markdown(data["new_rule_draft"])
                    st.subheader("リスクと確認事項")
                    st.table(data["risks_and_issues"])

                    # データベースへの保存
                    try:
                        st.info("分析結果をデータベースに保存しています...")
                        rule_data_to_insert = {
                            "current_rule": current_rule,
                            "law_amendment_points": law_amendment_points,
                            "reference_material": reference_text,
                            "new_rule_draft": data["new_rule_draft"],
                            "risk_analysis": json.dumps(data["risks_and_issues"])
                        }
                        supabase.table("rule_amendment_records").insert(rule_data_to_insert).execute()
                        st.success("データベースへの保存が完了しました。")
                    except Exception as db_e:
                        st.error(f"データベースへの保存中にエラーが発生しました: {db_e}")

                except (ValueError, json.JSONDecodeError):
                    st.error("応答からJSONを抽出できませんでした。")
                    st.text(raw_text)

            except Exception as e:
                st.error("APIの呼び出し中にエラーが発生しました。")
                st.exception(e)