"""Renombrar el rol supervisor a lider (Líder de Operaciones).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-21

Decisión de Máximo del 12/10/2026: el rol que evalúa criticidad, planifica y
confirma la ronda es el Líder de Operaciones, como dice el relevamiento.
Los usuarios que ya tenían el rol "supervisor" pasan a tener "lider".
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Se quita la restricción vieja, que solo admitía 'supervisor' y 'operador'.
    op.drop_constraint("ck_usuario_rol", "usuario", type_="check")
    # 2. Se actualizan los datos existentes.
    op.execute("UPDATE usuario SET rol = 'lider' WHERE rol = 'supervisor'")
    # 3. Se crea la restricción nueva.
    op.create_check_constraint("ck_usuario_rol", "usuario", "rol IN ('lider', 'operador')")


def downgrade() -> None:
    op.drop_constraint("ck_usuario_rol", "usuario", type_="check")
    op.execute("UPDATE usuario SET rol = 'supervisor' WHERE rol = 'lider'")
    op.create_check_constraint(
        "ck_usuario_rol", "usuario", "rol IN ('supervisor', 'operador')"
    )
