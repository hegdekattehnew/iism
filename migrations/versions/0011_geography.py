"""Geography master: states, districts, sub-districts

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-05

36 states, 767 districts and 7,138 sub-districts from the NSQF master data.

The district -> state link comes only from the array embedded in each state
document; the standalone `district` collection carries no state reference at
all, so the embedded copy is the authority for the hierarchy and for the policy
flags (aspirational, border, tribal, LWE, north-east) that skilling schemes
target.

Foreign keys are added *beside* the existing free-text location columns on jobs,
candidate profiles and preferred locations rather than replacing them. Not every
value resolves -- the seeded "Bengaluru" is "Bengaluru Urban" in the master --
and losing an unresolvable location would be worse than carrying both.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('states',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('state_code', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('slug', sa.String(length=160), nullable=False),
    sa.Column('ncvet_code', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_states_slug'), 'states', ['slug'], unique=True)
    op.create_index(op.f('ix_states_state_code'), 'states', ['state_code'], unique=True)
    op.create_table('districts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('district_code', sa.Integer(), nullable=False),
    sa.Column('state_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=True),
    sa.Column('slug', sa.String(length=200), nullable=True),
    sa.Column('short_name', sa.String(length=64), nullable=True),
    sa.Column('is_aspirational', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('is_border', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('is_tribal', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('is_lwe', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('is_north_east', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('is_rural_or_municipal', sa.Boolean(), server_default='false', nullable=False),
    sa.ForeignKeyConstraint(['state_id'], ['states.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_districts_district_code'), 'districts', ['district_code'], unique=True)
    op.create_index(op.f('ix_districts_slug'), 'districts', ['slug'], unique=True)
    op.create_index('ix_districts_state_id', 'districts', ['state_id'], unique=False)
    op.create_table('sub_districts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('district_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.ForeignKeyConstraint(['district_id'], ['districts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('district_id', 'name', name='uq_sub_district_name')
    )
    op.create_index(op.f('ix_sub_districts_code'), 'sub_districts', ['code'], unique=False)
    op.create_index('ix_sub_districts_district_id', 'sub_districts', ['district_id'], unique=False)
    op.add_column('candidate_preferred_locations', sa.Column('state_id', sa.Uuid(), nullable=True))
    op.add_column('candidate_preferred_locations', sa.Column('district_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_candidate_preferred_locations_district_id'), 'candidate_preferred_locations', ['district_id'], unique=False)
    op.create_index(op.f('ix_candidate_preferred_locations_state_id'), 'candidate_preferred_locations', ['state_id'], unique=False)
    op.create_foreign_key('fk_candidate_preferred_locations_district_id', 'candidate_preferred_locations', 'districts', ['district_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_candidate_preferred_locations_state_id', 'candidate_preferred_locations', 'states', ['state_id'], ['id'], ondelete='SET NULL')
    op.add_column('candidate_profiles', sa.Column('state_id', sa.Uuid(), nullable=True))
    op.add_column('candidate_profiles', sa.Column('district_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_candidate_profiles_district_id'), 'candidate_profiles', ['district_id'], unique=False)
    op.create_index(op.f('ix_candidate_profiles_state_id'), 'candidate_profiles', ['state_id'], unique=False)
    op.create_foreign_key('fk_candidate_profiles_state_id', 'candidate_profiles', 'states', ['state_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_candidate_profiles_district_id', 'candidate_profiles', 'districts', ['district_id'], ['id'], ondelete='SET NULL')
    op.add_column('jobs', sa.Column('state_id', sa.Uuid(), nullable=True))
    op.add_column('jobs', sa.Column('district_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_jobs_district_id'), 'jobs', ['district_id'], unique=False)
    op.create_index(op.f('ix_jobs_state_id'), 'jobs', ['state_id'], unique=False)
    op.create_foreign_key('fk_jobs_state_id', 'jobs', 'states', ['state_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_jobs_district_id', 'jobs', 'districts', ['district_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_jobs_state_id', 'jobs', type_='foreignkey')
    op.drop_constraint('fk_jobs_district_id', 'jobs', type_='foreignkey')
    op.drop_index(op.f('ix_jobs_state_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_district_id'), table_name='jobs')
    op.drop_column('jobs', 'district_id')
    op.drop_column('jobs', 'state_id')
    op.drop_constraint('fk_candidate_profiles_state_id', 'candidate_profiles', type_='foreignkey')
    op.drop_constraint('fk_candidate_profiles_district_id', 'candidate_profiles', type_='foreignkey')
    op.drop_index(op.f('ix_candidate_profiles_state_id'), table_name='candidate_profiles')
    op.drop_index(op.f('ix_candidate_profiles_district_id'), table_name='candidate_profiles')
    op.drop_column('candidate_profiles', 'district_id')
    op.drop_column('candidate_profiles', 'state_id')
    op.drop_constraint('fk_candidate_preferred_locations_state_id', 'candidate_preferred_locations', type_='foreignkey')
    op.drop_constraint('fk_candidate_preferred_locations_district_id', 'candidate_preferred_locations', type_='foreignkey')
    op.drop_index(op.f('ix_candidate_preferred_locations_state_id'), table_name='candidate_preferred_locations')
    op.drop_index(op.f('ix_candidate_preferred_locations_district_id'), table_name='candidate_preferred_locations')
    op.drop_column('candidate_preferred_locations', 'district_id')
    op.drop_column('candidate_preferred_locations', 'state_id')
    op.drop_index('ix_sub_districts_district_id', table_name='sub_districts')
    op.drop_index(op.f('ix_sub_districts_code'), table_name='sub_districts')
    op.drop_table('sub_districts')
    op.drop_index('ix_districts_state_id', table_name='districts')
    op.drop_index(op.f('ix_districts_slug'), table_name='districts')
    op.drop_index(op.f('ix_districts_district_code'), table_name='districts')
    op.drop_table('districts')
    op.drop_index(op.f('ix_states_state_code'), table_name='states')
    op.drop_index(op.f('ix_states_slug'), table_name='states')
    op.drop_table('states')
