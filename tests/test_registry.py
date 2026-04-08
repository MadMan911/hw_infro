import pytest

from src.agents.registry import AgentCard, AgentRegistry


@pytest.fixture
def registry():
    return AgentRegistry()


@pytest.fixture
def faq_card():
    return AgentCard(
        id="faq-agent",
        name="FAQ Agent",
        description="Answers frequently asked questions",
        supported_methods=["faq", "general_question"],
        supported_topics=["account", "password", "general"],
        llm_requirements={"preferred_model": "mock-model", "max_tokens": 500},
    )


@pytest.fixture
def billing_card():
    return AgentCard(
        id="billing-agent",
        name="Billing Agent",
        description="Handles billing and payment queries",
        supported_methods=["billing"],
        supported_topics=["payment", "invoice", "pricing"],
        llm_requirements={"preferred_model": "mock-model", "max_tokens": 800},
    )


class TestAgentCard:
    def test_defaults(self, faq_card):
        assert faq_card.version == "1.0.0"
        assert faq_card.status == "active"
        assert faq_card.registered_at is not None

    def test_custom_fields(self):
        card = AgentCard(
            id="x",
            name="X",
            description="x",
            version="2.0.0",
            supported_methods=["m"],
            supported_topics=["t"],
            status="inactive",
        )
        assert card.version == "2.0.0"
        assert card.status == "inactive"


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_and_get(self, registry, faq_card):
        await registry.register(faq_card)
        result = await registry.get("faq-agent")
        assert result.name == "FAQ Agent"

    @pytest.mark.asyncio
    async def test_register_overwrites(self, registry, faq_card):
        await registry.register(faq_card)
        updated = faq_card.model_copy(update={"name": "Updated FAQ"})
        await registry.register(updated)
        result = await registry.get("faq-agent")
        assert result.name == "Updated FAQ"


class TestUnregister:
    @pytest.mark.asyncio
    async def test_unregister(self, registry, faq_card):
        await registry.register(faq_card)
        await registry.unregister("faq-agent")
        with pytest.raises(KeyError):
            await registry.get("faq-agent")

    @pytest.mark.asyncio
    async def test_unregister_missing_raises(self, registry):
        with pytest.raises(KeyError, match="not found"):
            await registry.unregister("no-such-agent")


class TestGet:
    @pytest.mark.asyncio
    async def test_get_missing_raises(self, registry):
        with pytest.raises(KeyError, match="not found"):
            await registry.get("no-such-agent")


class TestListAll:
    @pytest.mark.asyncio
    async def test_empty(self, registry):
        assert await registry.list_all() == []

    @pytest.mark.asyncio
    async def test_returns_all(self, registry, faq_card, billing_card):
        await registry.register(faq_card)
        await registry.register(billing_card)
        result = await registry.list_all()
        assert len(result) == 2


class TestFindByMethod:
    @pytest.mark.asyncio
    async def test_finds_matching(self, registry, faq_card, billing_card):
        await registry.register(faq_card)
        await registry.register(billing_card)
        result = await registry.find_by_method("faq")
        assert len(result) == 1
        assert result[0].id == "faq-agent"

    @pytest.mark.asyncio
    async def test_excludes_inactive(self, registry, faq_card):
        faq_card.status = "inactive"
        await registry.register(faq_card)
        assert await registry.find_by_method("faq") == []

    @pytest.mark.asyncio
    async def test_no_match(self, registry, faq_card):
        await registry.register(faq_card)
        assert await registry.find_by_method("nonexistent") == []


class TestFindByTopic:
    @pytest.mark.asyncio
    async def test_finds_matching(self, registry, faq_card, billing_card):
        await registry.register(faq_card)
        await registry.register(billing_card)
        result = await registry.find_by_topic("payment")
        assert len(result) == 1
        assert result[0].id == "billing-agent"

    @pytest.mark.asyncio
    async def test_excludes_inactive(self, registry, billing_card):
        billing_card.status = "inactive"
        await registry.register(billing_card)
        assert await registry.find_by_topic("payment") == []
