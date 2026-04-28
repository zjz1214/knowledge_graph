"""
深度复习引擎
预先生成挑战性问题，存储到数据库
"""

import asyncio
import json
import httpx
from datetime import datetime, date
from typing import Optional
from app.core.database import db
from app.config import get_settings

settings = get_settings()
OLLAMA_URL = settings.ollama_base_url


class DeepReviewEngine:
    """深度复习引擎 - 预生成+存储模式"""

    def __init__(self):
        self.ollama_model = "llama3.2:latest"

    async def ensure_pregenerated(self, category: str = None, limit: int = 20):
        """
        确保有足够的预生成复习内容
        如果预生成内容不足，则生成新的
        """
        # 检查已有预生成内容数量
        existing = await self.get_pregenerated_count(category)
        print(f"当前预生成内容数量: {existing}, 需要: {limit}")

        if existing >= limit:
            print("预生成内容足够，无需生成")
            return

        # 生成新内容
        await self.generate_batch(category, limit - existing)

    async def get_pregenerated_count(self, category: str = None) -> int:
        """获取已预生成的内容数量（排除已删除的）"""
        if category:
            query = """
            MATCH (d:DeepReview)
            WHERE d.entity_category = $category
            AND d.is_deleted = false
            RETURN count(d) AS count
            """
            results = await db.execute_query(query, {"category": category})
        else:
            query = "MATCH (d:DeepReview) WHERE d.is_deleted = false RETURN count(d) AS count"
            results = await db.execute_query(query)

        return results[0]["count"] if results else 0

    async def get_pregenerated_session(self, category: str = None, limit: int = 10) -> list:
        """
        获取预生成的复习会话（排除已删除的）
        """
        if category:
            query = """
            MATCH (d:DeepReview)
            WHERE d.entity_category = $category
            AND d.is_deleted = false
            AND d.is_favorited = true
            RETURN d.id AS id, d
            ORDER BY d.created_at DESC
            LIMIT $limit
            """
            results = await db.execute_query(query, {"category": category, "limit": limit}) or []
        else:
            query = """
            MATCH (d:DeepReview)
            WHERE d.is_deleted = false
            AND d.is_favorited = true
            RETURN d.id AS id, d
            ORDER BY d.created_at DESC
            LIMIT $limit
            """
            results = await db.execute_query(query, {"limit": limit}) or []

        # 如果没有收藏的，返回全部预生成内容
        if not results:
            if category:
                query = """
                MATCH (d:DeepReview)
                WHERE d.entity_category = $category
                AND d.is_deleted = false
                RETURN d.id AS id, d
                ORDER BY d.importance_score DESC, d.created_at DESC
                LIMIT $limit
                """
                results = await db.execute_query(query, {"category": category, "limit": limit}) or []
            else:
                query = """
                MATCH (d:DeepReview)
                WHERE d.is_deleted = false
                RETURN d.id AS id, d
                ORDER BY d.importance_score DESC, d.created_at DESC
                LIMIT $limit
                """
                results = await db.execute_query(query, {"limit": limit}) or []

        return [self._parse_deep_review(r["d"], r.get("id")) for r in results]

    def _parse_deep_review(self, d: dict, review_id: str = None) -> dict:
        """解析预生成的复习内容"""
        return {
            "id": review_id or d.get("id"),
            "entity_id": d.get("entity_id"),
            "entity_label": d.get("entity_label"),
            "entity_description": d.get("entity_description"),
            "entity_type": d.get("entity_type"),
            "entity_category": d.get("entity_category"),
            "importance_score": d.get("importance_score", 0),
            "prerequisites": json.loads(d.get("prerequisites_json", "[]")),
            "siblings": json.loads(d.get("siblings_json", "[]")),
            "questions": json.loads(d.get("questions_json", "[]")),
            "is_favorited": d.get("is_favorited", False),
            "is_deleted": d.get("is_deleted", False),
            "created_at": d.get("created_at")
        }

    async def generate_batch(self, category: str = None, batch_size: int = 10):
        """
        批量生成复习内容
        """
        # 获取重要实体
        entities = await self._get_important_entities(category, batch_size * 2)
        print(f"获取到 {len(entities)} 个重要实体")

        generated = 0
        for entity in entities:
            if generated >= batch_size:
                break

            entity_id = entity.get("entity_id")
            label = entity.get("label")

            # 检查是否已存在
            existing = await self._get_existing_review(entity_id)
            if existing:
                continue

            # 获取上下文
            context = await self._get_entity_context(entity_id)

            # 生成问题
            questions = await self._generate_questions(entity, context)

            # 存储
            await self._store_deep_review(
                entity=entity,
                context=context,
                questions=questions
            )

            generated += 1
            print(f"已生成: {label} ({generated}/{batch_size})")

            await asyncio.sleep(0.5)  # 避免请求过快

        print(f"批量生成完成: {generated} 条")

    async def _get_important_entities(self, category: str = None, limit: int = 20) -> list:
        """获取重要实体列表"""
        if category:
            query = """
            MATCH (e:Entity)
            WHERE size(e.label) > 1 AND e.category = $category
            OPTIONAL MATCH (e)-[r]-()
            WITH e, count(r) AS connections
            OPTIONAL MATCH (e)<-[r2]-(pre:Entity)
            WHERE size(pre.label) > 1
            WITH e, connections, count(r2) AS prereq_count
            RETURN e.id AS entity_id,
                   e.label AS label,
                   e.description AS description,
                   e.type AS entity_type,
                   e.category AS category,
                   connections + prereq_count * 2 AS importance_score
            ORDER BY importance_score DESC
            LIMIT $limit
            """
            results = await db.execute_query(query, {"category": category, "limit": limit})
        else:
            query = """
            MATCH (e:Entity)
            WHERE size(e.label) > 1
            OPTIONAL MATCH (e)-[r]-()
            WITH e, count(r) AS connections
            OPTIONAL MATCH (e)<-[r2]-(pre:Entity)
            WHERE size(pre.label) > 1
            WITH e, connections, count(r2) AS prereq_count
            RETURN e.id AS entity_id,
                   e.label AS label,
                   e.description AS description,
                   e.type AS entity_type,
                   e.category AS category,
                   connections + prereq_count * 2 AS importance_score
            ORDER BY importance_score DESC
            LIMIT $limit
            """
            results = await db.execute_query(query, {"limit": limit})

        return results or []

    async def _get_entity_context(self, entity_id: str) -> dict:
        """获取实体上下文"""
        query = """
        MATCH (e:Entity {id: $id})

        OPTIONAL MATCH (e)<-[r1]-(pre:Entity)
        WHERE type(r1) IN ['uses', 'depends_on', 'part_of', 'defines']
        AND size(pre.label) > 1

        OPTIONAL MATCH (parent:Entity)-[r2]->(e)
        WHERE type(r2) IN ['part_of', 'defines']
        OPTIONAL MATCH (parent)-[r3]->(sibling:Entity)
        WHERE type(r3) IN ['part_of', 'defines']
        AND sibling.id <> e.id
        AND size(sibling.label) > 1

        OPTIONAL MATCH (e)-[r4]->(parent2:Entity)
        WHERE type(r4) IN ['part_of', 'defines', 'caused_by']

        RETURN e.id AS entity_id,
               e.label AS label,
               e.description AS description,
               e.type AS entity_type,
               e.category AS category,
               collect(DISTINCT {
                   role: 'prerequisite',
                   id: pre.id,
                   label: pre.label,
                   type: type(r1),
                   description: pre.description
               }) AS prerequisites,
               collect(DISTINCT {
                   role: 'sibling',
                   id: sibling.id,
                   label: sibling.label,
                   type: type(r3),
                   description: sibling.description
               }) AS siblings,
               collect(DISTINCT {
                   role: 'parent',
                   id: parent2.id,
                   label: parent2.label,
                   type: type(r4),
                   description: parent2.description
               }) AS parents
        """
        results = await db.execute_query(query, {"id": entity_id})
        return results[0] if results else {}

    async def _get_existing_review(self, entity_id: str) -> Optional[dict]:
        """检查是否已存在复习内容"""
        query = """
        MATCH (d:DeepReview {entity_id: $entity_id})
        RETURN d
        """
        results = await db.execute_query(query, {"entity_id": entity_id})
        return results[0]["d"] if results else None

    async def _generate_questions(self, entity: dict, context: dict) -> list:
        """生成挑战性问题"""
        entity_label = entity.get("label", "")
        entity_desc = entity.get("description", "")

        prerequisites = [p for p in (context.get("prerequisites") or []) if p.get("label")]
        siblings = [s for s in (context.get("siblings") or []) if s.get("label")]

        prompt = f"""针对「{entity_label}」这个概念生成3个深度理解问题。

概念描述：{entity_desc}

前置基础：{chr(10).join([f"- {p['label']}" for p in prerequisites[:3]]) if prerequisites else "无"}
易混淆概念：{chr(10).join([f"- {s['label']}" for s in siblings[:3]]) if siblings else "无"}

要求：问题类型包括区别类、联系类、原理类各一个。
每个 answer_hint 应该是对该问题的完整、清晰回答，包含：关键要点（what/why/how）、常见误区、与前置基础和易混淆概念的区分点。回答长度约 100-200 字。
输出JSON格式：
{{
  "questions": [
    {{
      "type": "distinction",
      "question": "区别类问题",
      "answer_hint": "完整的参考答案，包含与易混淆概念的对比和关键区分点"
    }},
    {{
      "type": "connection",
      "question": "联系类问题",
      "answer_hint": "完整的参考答案，说明联系、关系及背后的原因"
    }},
    {{
      "type": "principle",
      "question": "原理类问题",
      "answer_hint": "完整的参考答案，说明原理、工作机制或核心逻辑"
    }}
  ]
}}

只返回JSON。"""

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": self.ollama_model, "prompt": prompt, "stream": False}
                )
                result = response.json()
                text = result.get("response", "")
                return self._parse_questions(text)
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return []

    def _parse_questions(self, text: str) -> list:
        """解析问题 JSON"""
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                return data.get("questions", [])
        except:
            pass
        return []

    async def _store_deep_review(self, entity: dict, context: dict, questions: list):
        """存储预生成的复习内容"""
        prerequisites = [p for p in (context.get("prerequisites") or []) if p.get("label")]
        siblings = [s for s in (context.get("siblings") or []) if s.get("label")]

        query = """
        CREATE (d:DeepReview {
            id: randomUuid(),
            entity_id: $entity_id,
            entity_label: $entity_label,
            entity_description: $entity_description,
            entity_type: $entity_type,
            entity_category: $entity_category,
            importance_score: $importance_score,
            prerequisites_json: $prerequisites_json,
            siblings_json: $siblings_json,
            questions_json: $questions_json,
            is_favorited: false,
            is_deleted: false,
            created_at: datetime()
        })
        """
        try:
            await db.execute_write(query, {
                "entity_id": entity.get("entity_id"),
                "entity_label": entity.get("label"),
                "entity_description": entity.get("description", ""),
                "entity_type": entity.get("entity_type", "concept"),
                "entity_category": entity.get("category"),
                "importance_score": entity.get("importance_score", 0),
                "prerequisites_json": json.dumps(prerequisites[:5], ensure_ascii=False),
                "siblings_json": json.dumps(siblings[:5], ensure_ascii=False),
                "questions_json": json.dumps(questions, ensure_ascii=False)
            })
        except Exception as e:
            print(f"存储失败: {e}")

    async def toggle_favorite(self, review_id: str) -> bool:
        """切换收藏状态"""
        query = """
        MATCH (d:DeepReview {id: $id})
        SET d.is_favorited = NOT d.is_favorited
        RETURN d.is_favorited AS is_favorited
        """
        results = await db.execute_write(query, {"id": review_id})
        return results[0].get("is_favorited", False) if results else False

    async def delete_review(self, review_id: str) -> bool:
        """软删除复习内容"""
        query = """
        MATCH (d:DeepReview {id: $id})
        SET d.is_deleted = true
        """
        try:
            await db.execute_write(query, {"id": review_id})
            return True
        except:
            return False

    async def delete_entity(self, entity_id: str) -> bool:
        """删除实体及其相关复习内容"""
        query = """
        MATCH (e:Entity {id: $entity_id})
        DETACH DELETE e
        """
        try:
            await db.execute_write(query, {"entity_id": entity_id})
            # 同时删除相关复习内容
            await db.execute_write("""
                MATCH (d:DeepReview {entity_id: $entity_id})
                DELETE d
            """, {"entity_id": entity_id})
            return True
        except Exception as e:
            print(f"删除实体失败: {e}")
            return False

    async def favorite_entity(self, entity_id: str) -> bool:
        """收藏实体"""
        query = """
        MATCH (e:Entity {id: $entity_id})
        SET e.is_favorited = true
        """
        try:
            await db.execute_write(query, {"entity_id": entity_id})
            return True
        except:
            return False

    async def unfavorite_entity(self, entity_id: str) -> bool:
        """取消收藏实体"""
        query = """
        MATCH (e:Entity {id: $entity_id})
        SET e.is_favorited = false
        """
        try:
            await db.execute_write(query, {"entity_id": entity_id})
            return True
        except:
            return False

    async def evaluate_answer(
        self,
        review_id: str,
        question_index: int,
        user_answer: str
    ) -> dict:
        """
        费曼反馈评估
        """
        # 获取复习内容和问题
        query = """
        MATCH (d:DeepReview {id: $id})
        RETURN d
        """
        results = await db.execute_query(query, {"id": review_id})
        if not results:
            return {"error": "复习内容不存在"}

        d = results[0]["d"]
        questions = json.loads(d.get("questions_json", "[]"))

        if question_index >= len(questions):
            return {"error": "问题不存在"}

        question = questions[question_index]

        # 构建评估 prompt
        prompt = f"""概念：{d.get('entity_label')}
描述：{d.get('entity_description')}

问题：{question.get('question')}
参考回答：{question.get('answer_hint', '无')}

用户回答：{user_answer}

请评估用户回答的质量（0-10分），与参考回答对比后指出逻辑断层或可深化的地方。
输出JSON格式：
{{
  "score": 评分数字,
  "feedback": [
    {{
      "type": "gap|misconception|superficial",
      "point": "问题点",
      "question": "追问"
    }}
  ],
  "summary": "总结"
}}

只返回JSON。"""

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": self.ollama_model, "prompt": prompt, "stream": False}
                )
                result = response.json()
                text = result.get("response", "")
                evaluation = self._parse_feedback(text)
                evaluation["answer_hint"] = question.get("answer_hint", "")
                return evaluation
        except Exception as e:
            return {"score": 5, "feedback": [], "summary": f"评估服务暂时不可用: {e}", "answer_hint": question.get("answer_hint", "")}

    def _parse_feedback(self, text: str) -> dict:
        """解析反馈 JSON"""
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except:
            pass
        return {"score": 5, "feedback": [], "summary": text[:200]}


# 全局实例
deep_review_engine = DeepReviewEngine()
