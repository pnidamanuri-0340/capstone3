from finlit.agents.registry import AGENT_KEYS
from finlit.rag.retriever import AgentKnowledgeRetriever, search
from finlit.rag.store import KNOWLEDGE_DIR, chunk_markdown, collection_counts


def test_every_agent_has_knowledge_files():
    for key in AGENT_KEYS:
        assert list((KNOWLEDGE_DIR / key).glob("*.md")), key


def test_chunk_markdown_sections():
    text = "# Title\n\nIntro line.\n\n## First\nAlpha body.\n\n## Second\nBeta body.\n"
    chunks = chunk_markdown(text, "x/doc.md")
    assert [c.section for c in chunks] == ["First", "Second"]
    assert "Intro line." in chunks[0].text and chunks[0].text.startswith("Title - First")


def test_ingest_populates_each_collection(kb):
    assert all(n > 0 for n in kb.values())
    assert collection_counts() == kb


def test_search_finds_expected_section(kb):
    hits = search("tax_education", "wash sale rule tax-loss harvesting")
    assert hits[0]["section"] == "Tax-loss harvesting and the wash-sale rule"
    assert set(hits[0]) >= {"text", "source", "section", "score"}


def test_collections_are_isolated_per_agent(kb):
    hits = search("market_analysis", "Roth IRA income limits")
    assert all(h["source"].startswith("market_analysis/") for h in hits)


def test_langchain_retriever(kb):
    docs = AgentKnowledgeRetriever(agent="goal_planning", k=2).invoke("SMART goals")
    assert len(docs) == 2 and docs[0].metadata["section"] == "SMART goals"
