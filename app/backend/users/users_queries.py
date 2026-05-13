# users_queries.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict,Any


async def get_user_data_for_profile(
    session: AsyncSession,
    user_id: int
) -> Dict[str, Any]:
    """Аналитический запрос для профиля (natal charts, biorhythms и т.д.)"""
    result = await session.execute(
        text("""
        SELECT DISTINCT ON (u.id)
            u.id as user_id, u.primary_auth_method,
            p.birth_date, p.birth_time, p.birth_city,
            p.birth_lat, p.birth_lng, p.birth_timezone, p.profession,
            nc.planets, nc.aspects,
            pm.matrix_digits,
            b.physical_percentage
        FROM users u
        LEFT JOIN user_profiles p ON u.id = p.user_id
        LEFT JOIN natal_charts nc ON u.id = nc.user_id
            AND nc.id = (SELECT id FROM natal_charts WHERE user_id = u.id ORDER BY calculation_date DESC LIMIT 1)
        LEFT JOIN psyho_matrices pm ON u.id = pm.user_id
        LEFT JOIN biorhythms b ON u.id = b.user_id 
            AND b.calculation_date = (SELECT MAX(calculation_date) FROM biorhythms WHERE user_id = u.id)
        WHERE u.id = :user_id
        """),
        {"user_id": user_id}
    )
    row = result.fetchone()
    return dict(row._mapping) if row else {}
