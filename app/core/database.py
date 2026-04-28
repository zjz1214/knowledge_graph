from neo4j import AsyncGraphDatabase
from app.config import get_settings

settings = get_settings()


class Neo4jDatabase:
    """Neo4j database connection manager"""

    def __init__(self):
        self.driver = None

    async def connect(self):
        """Initialize Neo4j driver"""
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        # Test connection
        await self.driver.verify_connectivity()

    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()

    async def execute_query(self, query: str, params: dict = None):
        """Execute a Cypher query"""
        async with self.driver.session() as session:
            result = await session.run(query, params)
            return await result.data()

    async def execute_write(self, query: str, params: dict = None):
        """Execute a write transaction"""
        async with self.driver.session() as session:
            result = await session.run(query, params)
            return await result.data()

    async def init_indexes(self):
        """Initialize Neo4j indexes"""
        indexes = [
            # Entity indexes
            "CREATE INDEX entity_id IF NOT EXISTS FOR (e:Entity) ON (e.id)",
            "CREATE INDEX entity_label IF NOT EXISTS FOR (e:Entity) ON (e.label)",
            # Chunk indexes
            "CREATE INDEX chunk_id IF NOT EXISTS FOR (c:Chunk) ON (c.id)",
            # Card indexes
            "CREATE INDEX card_id IF NOT EXISTS FOR (c:Card) ON (c.id)",
            "CREATE INDEX card_next_review IF NOT EXISTS FOR (c:Card) ON (c.next_review)",
        ]
        for idx in indexes:
            try:
                await self.execute_query(idx)
            except Exception:
                pass  # Index may already exist


# Global instance
db = Neo4jDatabase()


async def get_db() -> Neo4jDatabase:
    """Dependency for FastAPI"""
    return db
