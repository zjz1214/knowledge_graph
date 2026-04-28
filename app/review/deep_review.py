"""
深度复习引擎
预先生成挑战性问题，存储到数据库
"""

import asyncio
import hashlib
import json
import random
import httpx
import re
from datetime import datetime, date
from typing import Optional
from app.core.database import db
from app.core.rag_engine import MiniMaxLLM
from app.config import get_settings

settings = get_settings()
OLLAMA_URL = settings.ollama_base_url


def _clean_text(text: str) -> str:
    """清洗文本中的非法字符和乱码，保证 UTF-8 完整性"""
    if not text:
        return ""
    # 移除控制字符（换行 TAB 回车保留）
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # 将连续的非可见 ASCII 乱码替换为 ?
    text = re.sub(r'[\x80-\xff]{2,}', lambda m: '?' * len(m.group()), text)
    # 移除孤立的高代理或低代理
    text = re.sub(r'[\ud800-\udfff]', '', text)
    return text.strip()


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
        """获取 active 状态的内容数量"""
        if category:
            query = """
            MATCH (d:DeepReview)
            WHERE d.entity_category = $category
            AND (d.review_status = 'active' OR d.review_status IS NULL)
            RETURN count(d) AS count
            """
            results = await db.execute_query(query, {"category": category})
        else:
            query = "MATCH (d:DeepReview) WHERE d.review_status = 'active' OR d.review_status IS NULL RETURN count(d) AS count"
            results = await db.execute_query(query)

        return results[0]["count"] if results else 0

    async def get_pregenerated_session(self, category: str = None, limit: int = 10) -> list:
        """
        获取 active 状态的复习会话，收藏置顶，其余按重要性排序
        """
        status_filter = "(d.review_status = 'active' OR d.review_status IS NULL)"

        if category:
            query = f"""
            MATCH (d:DeepReview)
            WHERE d.entity_category = $category
            AND {status_filter}
            RETURN d.id AS id, d
            ORDER BY d.is_favorited DESC, d.importance_score DESC, d.created_at DESC
            LIMIT $limit
            """
            results = await db.execute_query(query, {"category": category, "limit": limit}) or []
        else:
            query = f"""
            MATCH (d:DeepReview)
            WHERE {status_filter}
            RETURN d.id AS id, d
            ORDER BY d.is_favorited DESC, d.importance_score DESC, d.created_at DESC
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
            "review_status": d.get("review_status", "active"),
            "review_count": d.get("review_count", 0),
            "last_score": d.get("last_score", 0.0),
            "entity_hash": d.get("entity_hash", ""),
            "generation_version": d.get("generation_version", 1),
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
        entity_label = _clean_text(entity.get("label", ""))
        entity_desc = _clean_text(entity.get("description", ""))

        prerequisites = [_clean_text(p.get("label", "")) for p in (context.get("prerequisites") or []) if p.get("label")]
        siblings = [_clean_text(s.get("label", "")) for s in (context.get("siblings") or []) if s.get("label")]

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
        entity_desc = entity.get("description", "") or ""
        entity_hash = hashlib.md5(entity_desc.encode()).hexdigest()

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
            review_status: 'active',
            review_count: 0,
            last_score: 0.0,
            entity_hash: $entity_hash,
            generation_version: 1,
            created_at: datetime()
        })
        """
        try:
            await db.execute_write(query, {
                "entity_id": entity.get("entity_id"),
                "entity_label": entity.get("label"),
                "entity_description": entity_desc,
                "entity_type": entity.get("entity_type", "concept"),
                "entity_category": entity.get("category"),
                "importance_score": entity.get("importance_score", 0),
                "prerequisites_json": json.dumps(prerequisites[:5], ensure_ascii=False),
                "siblings_json": json.dumps(siblings[:5], ensure_ascii=False),
                "questions_json": json.dumps(questions, ensure_ascii=False),
                "entity_hash": entity_hash
            })
        except Exception as e:
            print(f"存储失败: {e}")

    async def record_review_event(
        self,
        review_id: str,
        question_index: int,
        question_text: str,
        user_answer: str,
        score: float,
        feedback_summary: str
    ) -> bool:
        """记录一次复习历史"""
        query = """
        MATCH (d:DeepReview {id: $review_id})
        CREATE (h:ReviewHistory {
            id: randomUuid(),
            review_id: $review_id,
            question_index: $question_index,
            question_text: $question_text,
            user_answer: $user_answer,
            score: $score,
            feedback_summary: $feedback_summary,
            created_at: datetime()
        })
        CREATE (d)-[:HAS_HISTORY]->(h)
        """
        try:
            await db.execute_write(query, {
                "review_id": review_id,
                "question_index": question_index,
                "question_text": question_text,
                "user_answer": user_answer,
                "score": float(score),
                "feedback_summary": feedback_summary
            })
            return True
        except Exception as e:
            print(f"记录历史失败: {e}")
            return False

    async def get_review_history(self, review_id: str) -> list:
        """获取某卡片的完整复习历史"""
        query = """
        MATCH (d:DeepReview {id: $review_id})-[:HAS_HISTORY]->(h:ReviewHistory)
        RETURN h
        ORDER BY h.created_at DESC
        """
        results = await db.execute_query(query, {"review_id": review_id}) or []
        return [self._parse_review_history(r["h"]) for r in results]

    def _parse_review_history(self, h: dict) -> dict:
        """解析复习历史记录"""
        created = h.get("created_at")
        if hasattr(created, "isoformat"):
            created = created.isoformat()
        return {
            "id": h.get("id"),
            "review_id": h.get("review_id"),
            "question_index": h.get("question_index"),
            "question_text": h.get("question_text"),
            "user_answer": h.get("user_answer"),
            "score": h.get("score", 0),
            "feedback_summary": h.get("feedback_summary", ""),
            "created_at": created
        }

    async def keep_review(self, review_id: str) -> bool:
        """标记为保留"""
        query = """
        MATCH (d:DeepReview {id: $id})
        SET d.review_status = 'kept'
        """
        try:
            await db.execute_write(query, {"id": review_id})
            return True
        except Exception as e:
            print(f"保留失败: {e}")
            return False

    async def discard_review(self, review_id: str) -> bool:
        """标记为丢弃"""
        query = """
        MATCH (d:DeepReview {id: $id})
        SET d.review_status = 'discarded'
        """
        try:
            await db.execute_write(query, {"id": review_id})
            return True
        except Exception as e:
            print(f"丢弃失败: {e}")
            return False

    async def check_entity_changed(self, entity_id: str, stored_hash: str) -> bool:
        """检查实体描述是否变化"""
        query = """
        MATCH (e:Entity {id: $entity_id})
        RETURN e.description AS description
        """
        results = await db.execute_query(query, {"entity_id": entity_id})
        if not results:
            return True
        current_desc = results[0].get("description") or ""
        current_hash = hashlib.md5(current_desc.encode()).hexdigest()
        return current_hash != stored_hash

    async def regenerate_questions(self, review_id: str, force: bool = False) -> dict:
        """重新生成问题"""
        query = """
        MATCH (d:DeepReview {id: $id})
        RETURN d
        """
        results = await db.execute_query(query, {"id": review_id})
        if not results:
            return {"error": "复习内容不存在"}
        d = results[0]["d"]
        entity_id = d.get("entity_id")
        stored_hash = d.get("entity_hash", "")
        changed = await self.check_entity_changed(entity_id, stored_hash)

        if not changed and not force:
            return {
                "error": "实体描述未变化，无需重新生成",
                "changed": False,
                "force_needed": True
            }

        context = await self._get_entity_context(entity_id)
        entity_info = {
            "entity_id": entity_id,
            "label": d.get("entity_label", ""),
            "description": d.get("entity_description", ""),
            "entity_type": d.get("entity_type", "concept"),
            "category": d.get("entity_category"),
        }
        questions = await self._generate_questions(entity_info, context)
        if not questions:
            return {"error": "生成失败，请重试"}

        new_hash = hashlib.md5((d.get("entity_description") or "").encode()).hexdigest()
        await db.execute_write("""
            MATCH (d:DeepReview {id: $id})
            SET d.questions_json = $questions_json,
                d.entity_hash = $entity_hash,
                d.generation_version = COALESCE(d.generation_version, 1) + 1
        """, {
            "id": review_id,
            "questions_json": json.dumps(questions, ensure_ascii=False),
            "entity_hash": new_hash
        })
        return {
            "review_id": review_id,
            "questions": questions,
            "changed": changed,
            "regeneration_count": d.get("generation_version", 1) + 1
        }

    async def get_entity_reviews(self, entity_id: str) -> list:
        """获取某实体的所有复习卡片"""
        query = """
        MATCH (d:DeepReview {entity_id: $entity_id})
        RETURN d.id AS id, d
        ORDER BY d.generation_version DESC
        """
        results = await db.execute_query(query, {"entity_id": entity_id}) or []
        return [self._parse_deep_review(r["d"], r.get("id")) for r in results]

    async def _generate_answer_hint(self, entity_label: str, entity_desc: str, question_text: str, question_type: str) -> str:
        """针对缺失 answer_hint 的旧卡片，实时生成参考答案（使用 MiniMax）"""
        entity_label = _clean_text(entity_label)
        entity_desc = _clean_text(entity_desc)
        question_text = _clean_text(question_text)

        system_prompt = "你是一个专业的知识讲解助手，擅长用清晰、准确的语言解释概念。回答时只输出答案，不要任何前缀说明。"
        prompt = f"""针对概念「{entity_label}」（描述：{entity_desc}）的问题「{question_text}」，生成一个完整、清晰的参考答案。

要求：
- 包含该概念的关键要点（what/why/how）
- 如果是区别类问题，说明与易混淆概念的区分点
- 如果是联系类问题，说明与其他概念的关系和原因
- 如果是原理类问题，说明工作机制或核心逻辑
- 长度约 100-200 字
- 只返回参考答案文本，不要加前缀如"参考答案："等"""

        try:
            llm = MiniMaxLLM()
            text = await llm.generate(prompt=prompt, system_prompt=system_prompt)
            text = text.strip()
            return text if text else "（暂无参考答案）"
        except Exception as e:
            return f"（参考答案生成失败：{e}）"

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
        """软删除复习内容（兼容旧接口，映射为 discard）"""
        return await self.discard_review(review_id)

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
        费曼反馈评估，并记录历史
        """
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
        stored_hint = question.get("answer_hint", "")

        # 如果没有参考答案，实时生成
        if not stored_hint:
            stored_hint = await self._generate_answer_hint(
                entity_label=d.get("entity_label", ""),
                entity_desc=d.get("entity_description", ""),
                question_text=question.get("question", ""),
                question_type=question.get("type", "")
            )

        entity_label = _clean_text(d.get("entity_label", ""))
        entity_desc = _clean_text(d.get("entity_description", ""))
        question_text = _clean_text(question.get("question", ""))
        prompt = f"""概念：{entity_label}
描述：{entity_desc}

问题：{question_text}
参考回答：{stored_hint}

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

        score = 5
        feedback_summary = ""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": self.ollama_model, "prompt": prompt, "stream": False}
                )
                result = response.json()
                text = result.get("response", "")
                evaluation = self._parse_feedback(text)
                score = evaluation.get("score", 5)
                feedback_summary = evaluation.get("summary", "")
                evaluation["answer_hint"] = stored_hint
                # 记录历史
                await self.record_review_event(
                    review_id=review_id,
                    question_index=question_index,
                    question_text=question.get("question", ""),
                    user_answer=user_answer,
                    score=score,
                    feedback_summary=feedback_summary
                )
                # 更新 DeepReview 的 review_count 和 last_score
                await db.execute_write("""
                    MATCH (d:DeepReview {id: $id})
                    SET d.review_count = COALESCE(d.review_count, 0) + 1,
                        d.last_score = $score
                """, {"id": review_id, "score": float(score)})
                return evaluation
        except Exception as e:
            return {"score": 5, "feedback": [], "summary": f"评估服务暂时不可用: {e}", "answer_hint": question.get("answer_hint", "")}

    def _parse_feedback(self, text: str) -> dict:
        """解析反馈 JSON，解析失败时返回明确的 error 状态"""
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                # 确保结构完整
                if "score" in data and "feedback" in data:
                    return data
        except:
            pass
        # 解析失败：返回 error 状态，不返回原始文本片段
        return {"error": "解析失败", "score": 5, "feedback": [], "summary": "评估服务返回格式异常，已忽略"}


# 全局实例
deep_review_engine = DeepReviewEngine()
