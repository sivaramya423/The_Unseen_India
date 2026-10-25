"""THE UNSEEN INDIA - Streamlit app.  Run with:  python -m streamlit run app.py"""
from html import escape as esc

import streamlit as st

import config
from services.discovery_engine import (EDUCATION_LEVELS, INDIAN_STATES, build_profile,
                                       distinct_categories, is_profile_empty, rank_opportunities,
                                       retrieve_for_question)
from services.groq_service import ask_question, check_connection
from services.knowledge_connections import METHOD_DESCRIPTION, find_connections
from services.knowledge_gap_detector import (KIND_ABSENT, KIND_UNVERIFIED, NOT_PROOF_NOTE,
                                             analyze_question, coverage_table, record_gaps)
from utils.data_loader import load_opportunities
from utils.ui import (badge, compare_table, inject_css, notice, opportunity_card, render_hero)
from utils.validators import check_question

st.set_page_config(page_title="THE UNSEEN INDIA", page_icon="🧭", layout="wide")
inject_css()


@st.cache_data(show_spinner=False)
def get_data():
    return load_opportunities()


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def sidebar() -> None:
    with st.sidebar:
        st.subheader("AI connection")
        key_found = bool(config.get_api_key())
        st.write("API key: " + ("found" if key_found else "not found"))
        st.write(f"Model: {config.get_model()}")
        if not key_found:
            st.info("The AI features are off until you add GROQ_API_KEY to a .env file. "
                    "Everything else works without it.")
        if st.button("Test Groq connection"):
            with st.spinner("Asking Groq which models your key can use..."):
                result = check_connection()
            if result.ok:
                (st.success if result.details["model_available"] else st.warning)(result.message)
                with st.expander("Models your key can see"):
                    st.write(result.details["models"])
            else:
                st.error(result.message)
        st.caption("The key is read from your .env file and is never shown here.")


def tab_radar(records: list) -> None:
    st.subheader("Opportunity Radar")
    st.caption("Describe your situation. Records are ranked by transparent rules over our dataset; "
               "no AI is used for the ranking.")
    with st.form("radar_form"):
        text = st.text_area(
            "What are you looking for?", height=110,
            placeholder="Example: I am studying AI and Data Science in Tamil Nadu. My family has limited "
                        "income, and I want to learn new skills, but I don't know which programmes are available.")
        with st.expander("Add details (optional)"):
            c1, c2, c3 = st.columns(3)
            level = c1.selectbox("Education level", ["Not specified"] + [l.title() for l in EDUCATION_LEVELS])
            state = c2.selectbox("State or union territory", ["Not specified"] + INDIAN_STATES)
            category = c3.selectbox("Opportunity category", ["Any"] + distinct_categories(records))
            interests = st.text_input("Interests or skills (comma separated)", placeholder="coding, design")
            notes = st.text_input("Anything else about eligibility (optional)",
                                  placeholder="for example: first-generation learner")
        submitted = st.form_submit_button("Discover opportunities", type="primary")

    if submitted:
        profile = build_profile(
            free_text=text,
            education_level="" if level == "Not specified" else level,
            state="" if state == "Not specified" else state,
            interests=[i for i in interests.split(",")],
            category="" if category == "Any" else category,
            eligibility_notes=notes)
        if is_profile_empty(profile):
            st.session_state["radar"] = None
            st.warning("Add a few words about yourself or pick at least one detail, then try again.")
        else:
            st.session_state["radar"] = {"profile": profile, "text": text,
                                         "results": rank_opportunities(records, profile, top_k=8)}

    radar = st.session_state.get("radar")
    if not radar:
        html(notice("Nothing to show yet.", "Results appear here after you describe your situation."))
        return
    profile, results = radar["profile"], radar["results"]
    understood = []
    if profile["state"]:
        understood.append(f"State: {profile['state']}")
    if profile["education_level"]:
        understood.append(f"Education: {profile['education_level']}")
    if profile["category"]:
        understood.append(f"Category: {profile['category']}")
    if profile["interests"]:
        understood.append("Interests: " + ", ".join(profile["interests"]))
    html('<div class="ui-note"><b>What we understood:</b> ' + (" | ".join(understood) or "only keywords from your text")
         + ". If something is wrong, use the optional details to correct it.</div>")
    if not results:
        st.info("No records in our dataset matched. That describes our dataset, not what exists in India. "
                "Try broader words, or check the official portals directly.")
        return
    st.success(f"{len(results)} record(s) matched. Scores are rule points, not probabilities.")
    for item in results:
        html(opportunity_card(item["record"], reasons=item["reasons"],
                              missing_fields=item["missing_fields"], strength=item["strength"],
                              score=item["score"]))
    if st.button("Explain these matches in plain language (uses the AI)"):
        question = radar["text"] or "Which of these records suit me and what should I check next?"
        with st.spinner("Asking the AI..."):
            answer = ask_question(question, results)
        show_ai_answer(answer)


def show_ai_answer(answer) -> None:
    if not answer.ok:
        st.error(answer.message)
        return
    st.markdown(answer.text)
    for warning in answer.warnings:
        st.warning(warning)
    html("<p><b>Sources used (links come from our dataset, not from the AI)</b></p>")
    for s in answer.sources:
        st.markdown(f"- [{s['name']}]({s['url']}) ({s['status'].replace('_', ' ')})")
    st.caption(f"Model: {answer.model}. Always confirm details on the official source before applying.")


def tab_connections(records: list) -> None:
    st.subheader("Knowledge Connections")
    html(notice("Method.", METHOD_DESCRIPTION))
    names = {r["name"]: r["id"] for r in records}
    chosen = st.selectbox("Pick a record to see what it connects to", list(names))
    connections = find_connections(records, names[chosen], top_k=5)
    if not connections:
        st.info("No other record shares enough attributes with this one.")
        return
    for c in connections:
        html(f'<div class="ui-card"><h3>{esc(c["record"]["name"])}</h3>'
             f'<div class="ui-bar"><div style="width:{int(c["score"] * 100)}%"></div></div>'
             f'<p>Connection strength {c["score"]:.2f} (0 to 1)</p>'
             + "<ul class='ui-list'>" + "".join(f"<li>{esc(r)}</li>" for r in c["reasons"]) + "</ul></div>")


def tab_gaps(records: list) -> None:
    st.subheader("Knowledge Gap Detector")
    html(notice("Three situations are kept apart.",
                "1) Absent from our dataset. 2) Recorded but unverified. 3) Does not exist: this tool never "
                "claims that, because only an official source can show it."))
    question = st.text_input("Ask something to see what the dataset can and cannot answer",
                             placeholder="Is a deadline available for scholarships in Tamil Nadu?", key="gap_q")
    if st.button("Check the dataset", key="gap_btn"):
        ok, message = check_question(question)
        if not ok:
            st.warning(message)
        else:
            result = analyze_question(records, question)
            if not result["ok"]:
                st.warning(result["message"])
            for f in result["findings"]:
                tone = {"absent_from_dataset": "bad", KIND_UNVERIFIED: "warn"}.get(f["kind"], "ok")
                label = {"absent_from_dataset": "Absent from dataset", KIND_UNVERIFIED: "Unverified"}.get(f["kind"], "Info")
                html(f'<div class="ui-card">{badge(label, tone)}<p><b>{esc(f["title"])}</b></p>'
                     f'<p>{esc(f["detail"])}</p><p><b>Next step:</b> {esc(f["next_step"])}</p></div>')
    st.markdown("#### Gaps in one record")
    names = {r["name"]: r for r in records}
    record = names[st.selectbox("Record", list(names), key="gap_record")]
    for gap in record_gaps(record):
        tone = "bad" if gap["kind"] == KIND_ABSENT else "warn"
        label = "Absent from dataset" if gap["kind"] == KIND_ABSENT else "Unverified"
        html(f'<div class="ui-card">{badge(label, tone)}<p>{esc(gap["message"])}</p>'
             f'<p><b>Next step:</b> {esc(gap["next_step"])}</p></div>')
    st.markdown("#### Dataset coverage")
    st.dataframe(coverage_table(records), hide_index=True)
    st.caption(NOT_PROOF_NOTE)


def tab_assistant(records: list) -> None:
    st.subheader("Evidence-based assistant")
    st.caption("Retrieves matching records first, then asks the AI to answer from those records only.")
    question = st.text_area("Your question", height=100, key="assistant_q",
                            placeholder="Which skill-development options in Tamil Nadu should I look at first?")
    if st.button("Ask using dataset records", type="primary", key="assistant_btn"):
        ok, message = check_question(question)
        if not ok:
            st.warning(message)
            return
        retrieved = retrieve_for_question(records, question, top_k=config.RETRIEVAL_TOP_K)
        with st.expander(f"Records retrieved as evidence ({len(retrieved)})", expanded=not retrieved):
            if not retrieved:
                st.write("No records matched this question.")
            for item in retrieved:
                st.markdown(f"- **{item['record']['name']}**: " + " ".join(item["reasons"]))
        with st.spinner("Asking the AI..."):
            answer = ask_question(question, retrieved)
        show_ai_answer(answer)
        if not answer.ok and retrieved:
            st.info("The AI is unavailable, but the retrieved records above are still useful. "
                    "Open the Opportunity Radar tab for full details.")


def tab_compare(records: list) -> None:
    st.subheader("Compare opportunities")
    names = {r["name"]: r for r in records}
    picked = st.multiselect("Choose two or three records", list(names), max_selections=3)
    if len(picked) < 2:
        st.info("Pick at least two records to compare them side by side.")
        return
    html(compare_table([names[p] for p in picked]))
    st.caption("Only information stored in our dataset is shown. 'Not available' means we do not have it.")


def tab_about(records: list, problems: list) -> None:
    st.subheader("Trust and transparency")
    st.markdown(
        "**What this prototype does:** matches your description against a small, hand-built dataset using "
        "transparent rules, connects related records, shows what is missing, and lets an AI explain the "
        "retrieved records.\n\n"
        "**What it does not do:** search the live web, check deadlines automatically, or cover every "
        "opportunity in India. Most records are portal references, not specific schemes.\n\n"
        "**What the AI knows:** only the records passed to it for each question. It is told not to add "
        "anything else, and links shown under its answers come from our dataset.")
    st.markdown("#### Where each record comes from")
    for r in records:
        st.markdown(f"- [{r['name']}]({r['official_source_url']}): {r['verification_status'].replace('_', ' ')}"
                    + (f", last verified {r['last_verified']}" if r.get("last_verified") else ", not verified yet"))
    if problems:
        with st.expander("Dataset problems found while loading"):
            for p in problems:
                st.write(p)
    st.markdown("#### Implemented, heuristic, LLM, future")
    st.markdown(
        "- **Rule-based (no AI):** Radar ranking, Knowledge Connections, Gap Detector, Comparison.\n"
        "- **LLM:** the plain-language explanations in the Assistant and the Radar button.\n"
        "- **Not built yet:** live web retrieval, automatic verification, semantic search, user accounts.")


def main() -> None:
    records, problems = get_data()
    render_hero(records)
    sidebar()
    if not records:
        st.error("The dataset could not be loaded, so the app cannot show opportunities.")
        for p in problems:
            st.write(p)
        return
    if problems:
        st.warning(f"{len(problems)} dataset record(s) were skipped. See Trust and transparency for details.")
    tabs = st.tabs(["Opportunity Radar", "Connections", "Gap Detector", "AI Assistant", "Compare",
                    "Trust and About"])
    with tabs[0]:
        tab_radar(records)
    with tabs[1]:
        tab_connections(records)
    with tabs[2]:
        tab_gaps(records)
    with tabs[3]:
        tab_assistant(records)
    with tabs[4]:
        tab_compare(records)
    with tabs[5]:
        tab_about(records, problems)


main()
