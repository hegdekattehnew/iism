--
-- PostgreSQL database dump
--

\restrict DoVRoHJzDILhvI2x0JB8dHF4yoW639oX8AoRfRtljTVMBG0Xcbx79g8jLvOe1Yx

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg12+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg12+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: analytics_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.analytics_events (
    id uuid NOT NULL,
    name character varying(64) NOT NULL,
    user_id uuid,
    subject_type character varying(32),
    subject_id uuid,
    payload jsonb,
    occurred_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_analytics_event_name CHECK (((name)::text = ANY ((ARRAY['matches_viewed'::character varying, 'match_opened'::character varying, 'gap_viewed'::character varying, 'course_recommended'::character varying, 'course_opened'::character varying, 'employer_overview_viewed'::character varying, 'employer_shortlist_viewed'::character varying])::text[])))
);


--
-- Name: awarding_bodies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.awarding_bodies (
    id uuid NOT NULL,
    code character varying(32) NOT NULL,
    body_ref character varying(32),
    name_en text NOT NULL,
    name_hi text,
    slug character varying(360) NOT NULL,
    body_type character varying(32) NOT NULL,
    logo_url character varying(1024),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_awarding_body_type CHECK (((body_type)::text = ANY ((ARRAY['sector_skill_council'::character varying, 'awarding_body'::character varying])::text[])))
);


--
-- Name: candidate_certifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_certifications (
    id uuid NOT NULL,
    profile_id uuid NOT NULL,
    name character varying NOT NULL,
    issuing_body character varying,
    credential_id character varying,
    issued_on date,
    expires_on date,
    nsqf_level numeric(3,1),
    skill_id uuid,
    CONSTRAINT ck_certification_dates CHECK (((expires_on IS NULL) OR (issued_on IS NULL) OR (expires_on >= issued_on)))
);


--
-- Name: candidate_educations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_educations (
    id uuid NOT NULL,
    profile_id uuid NOT NULL,
    qualification character varying NOT NULL,
    institution character varying,
    specialisation character varying,
    education_level character varying,
    year_completed integer,
    is_pursuing boolean NOT NULL,
    CONSTRAINT ck_education_year CHECK (((year_completed IS NULL) OR ((year_completed >= 1950) AND (year_completed <= 2100))))
);


--
-- Name: candidate_experiences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_experiences (
    id uuid NOT NULL,
    profile_id uuid NOT NULL,
    employer_name character varying NOT NULL,
    role_title character varying NOT NULL,
    location character varying,
    started_on date NOT NULL,
    ended_on date,
    is_current boolean NOT NULL,
    description character varying,
    CONSTRAINT ck_experience_current CHECK (((is_current = false) OR (ended_on IS NULL))),
    CONSTRAINT ck_experience_dates CHECK (((ended_on IS NULL) OR (ended_on >= started_on)))
);


--
-- Name: candidate_languages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_languages (
    id uuid NOT NULL,
    profile_id uuid NOT NULL,
    language character varying NOT NULL,
    proficiency character varying NOT NULL,
    can_read boolean NOT NULL,
    can_write boolean NOT NULL,
    CONSTRAINT ck_language_proficiency CHECK (((proficiency)::text = ANY ((ARRAY['basic'::character varying, 'conversational'::character varying, 'fluent'::character varying, 'native'::character varying])::text[])))
);


--
-- Name: candidate_preferred_locations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_preferred_locations (
    id uuid NOT NULL,
    profile_id uuid NOT NULL,
    state character varying NOT NULL,
    district character varying,
    state_id uuid,
    district_id uuid
);


--
-- Name: candidate_preferred_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_preferred_roles (
    id uuid NOT NULL,
    profile_id uuid NOT NULL,
    title character varying NOT NULL
);


--
-- Name: candidate_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_profiles (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    headline character varying,
    location_state character varying,
    location_district character varying,
    years_experience integer NOT NULL,
    education_level character varying,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    date_of_birth date,
    gender character varying,
    willing_to_relocate boolean DEFAULT false NOT NULL,
    preferred_employment_type character varying,
    expected_salary_min_inr integer,
    expected_salary_max_inr integer,
    notice_period character varying,
    onboarding_completed_at timestamp with time zone,
    state_id uuid,
    district_id uuid,
    CONSTRAINT ck_candidate_experience CHECK (((years_experience >= 0) AND (years_experience <= 60))),
    CONSTRAINT ck_candidate_gender CHECK (((gender IS NULL) OR ((gender)::text = ANY ((ARRAY['female'::character varying, 'male'::character varying, 'other'::character varying, 'prefer_not_to_say'::character varying])::text[])))),
    CONSTRAINT ck_candidate_notice CHECK (((notice_period IS NULL) OR ((notice_period)::text = ANY ((ARRAY['immediate'::character varying, 'within_15_days'::character varying, 'within_30_days'::character varying, 'over_30_days'::character varying])::text[])))),
    CONSTRAINT ck_candidate_salary_range CHECK (((expected_salary_min_inr IS NULL) OR (expected_salary_max_inr IS NULL) OR (expected_salary_max_inr >= expected_salary_min_inr)))
);


--
-- Name: candidate_skills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candidate_skills (
    id uuid NOT NULL,
    profile_id uuid NOT NULL,
    skill_id uuid NOT NULL,
    proficiency integer NOT NULL,
    source character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_candidate_skill_proficiency CHECK (((proficiency >= 1) AND (proficiency <= 5))),
    CONSTRAINT ck_candidate_skill_source CHECK (((source)::text = ANY ((ARRAY['self_declared'::character varying, 'inferred'::character varying, 'assessed'::character varying, 'certified'::character varying])::text[])))
);


--
-- Name: course_skills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.course_skills (
    id uuid NOT NULL,
    course_id uuid NOT NULL,
    skill_id uuid NOT NULL,
    level_taught numeric(3,1),
    CONSTRAINT ck_course_skill_level CHECK (((level_taught IS NULL) OR ((level_taught >= (1)::numeric) AND (level_taught <= (10)::numeric))))
);


--
-- Name: courses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.courses (
    id uuid NOT NULL,
    slug character varying NOT NULL,
    tenant_id uuid NOT NULL,
    title_en character varying NOT NULL,
    title_hi character varying,
    description_en character varying,
    description_hi character varying,
    mode character varying NOT NULL,
    language character varying NOT NULL,
    duration_hours integer,
    fee_inr integer,
    nsqf_level numeric(3,1),
    qualification_pack_code character varying,
    status character varying NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS ((((setweight(to_tsvector('english'::regconfig, (COALESCE(title_en, ''::character varying))::text), 'A'::"char") || setweight(to_tsvector('simple'::regconfig, (COALESCE(title_hi, ''::character varying))::text), 'A'::"char")) || setweight(to_tsvector('english'::regconfig, (COALESCE(description_en, ''::character varying))::text), 'C'::"char")) || setweight(to_tsvector('simple'::regconfig, (COALESCE(description_hi, ''::character varying))::text), 'C'::"char"))) STORED,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_courses_language CHECK (((language)::text = ANY ((ARRAY['en'::character varying, 'hi'::character varying, 'both'::character varying])::text[]))),
    CONSTRAINT ck_courses_mode CHECK (((mode)::text = ANY ((ARRAY['online'::character varying, 'offline'::character varying, 'hybrid'::character varying])::text[]))),
    CONSTRAINT ck_courses_nsqf_level CHECK (((nsqf_level IS NULL) OR ((nsqf_level >= (1)::numeric) AND (nsqf_level <= (10)::numeric)))),
    CONSTRAINT ck_courses_status CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'published'::character varying])::text[])))
);


--
-- Name: districts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.districts (
    id uuid NOT NULL,
    district_code integer NOT NULL,
    state_id uuid NOT NULL,
    name character varying(160),
    slug character varying(200),
    short_name character varying(64),
    is_aspirational boolean DEFAULT false NOT NULL,
    is_border boolean DEFAULT false NOT NULL,
    is_tribal boolean DEFAULT false NOT NULL,
    is_lwe boolean DEFAULT false NOT NULL,
    is_north_east boolean DEFAULT false NOT NULL,
    is_rural_or_municipal boolean DEFAULT false NOT NULL
);


--
-- Name: job_skills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.job_skills (
    id uuid NOT NULL,
    job_id uuid NOT NULL,
    skill_id uuid NOT NULL,
    importance integer NOT NULL,
    is_mandatory boolean NOT NULL,
    CONSTRAINT ck_job_skill_importance CHECK (((importance >= 1) AND (importance <= 5)))
);


--
-- Name: jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.jobs (
    id uuid NOT NULL,
    slug character varying NOT NULL,
    tenant_id uuid NOT NULL,
    title_en character varying NOT NULL,
    title_hi character varying,
    description_en character varying,
    description_hi character varying,
    location_state character varying,
    location_district character varying,
    employment_type character varying NOT NULL,
    experience_min_years integer NOT NULL,
    experience_max_years integer,
    salary_min_inr integer,
    salary_max_inr integer,
    nsqf_level_min numeric(3,1),
    status character varying NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS ((((setweight(to_tsvector('english'::regconfig, (COALESCE(title_en, ''::character varying))::text), 'A'::"char") || setweight(to_tsvector('simple'::regconfig, (COALESCE(title_hi, ''::character varying))::text), 'A'::"char")) || setweight(to_tsvector('english'::regconfig, (COALESCE(description_en, ''::character varying))::text), 'C'::"char")) || setweight(to_tsvector('simple'::regconfig, (COALESCE(description_hi, ''::character varying))::text), 'C'::"char"))) STORED,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    state_id uuid,
    district_id uuid,
    CONSTRAINT ck_jobs_employment_type CHECK (((employment_type)::text = ANY ((ARRAY['full_time'::character varying, 'part_time'::character varying, 'contract'::character varying, 'apprenticeship'::character varying])::text[]))),
    CONSTRAINT ck_jobs_nsqf_level CHECK (((nsqf_level_min IS NULL) OR ((nsqf_level_min >= (1)::numeric) AND (nsqf_level_min <= (10)::numeric)))),
    CONSTRAINT ck_jobs_status CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'published'::character varying])::text[])))
);


--
-- Name: memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.memberships (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    role character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_membership_role CHECK (((role)::text = ANY ((ARRAY['owner'::character varying, 'admin'::character varying, 'member'::character varying])::text[])))
);


--
-- Name: model_curricula; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.model_curricula (
    id uuid NOT NULL,
    qp_code character varying NOT NULL,
    mc_version character varying NOT NULL,
    qp_id uuid,
    job_role_en character varying,
    nsqf_level numeric(3,1),
    status character varying,
    total_minutes integer,
    document_ref character varying(1024),
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: occupations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.occupations (
    id uuid NOT NULL,
    name_en text NOT NULL,
    name_hi text,
    occupation_ref character varying(64) NOT NULL,
    code character varying(16),
    sector_id uuid NOT NULL
);


--
-- Name: qp_entry_routes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qp_entry_routes (
    id uuid NOT NULL,
    qp_id uuid NOT NULL,
    ordinal integer NOT NULL,
    education_ref character varying(32),
    education_desc text,
    education_specialisation text,
    experience_ref character varying(32),
    experience_desc character varying(64),
    experience_specialisation text,
    experience_years numeric(4,1)
);


--
-- Name: qp_nco_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qp_nco_codes (
    id uuid NOT NULL,
    qp_id uuid NOT NULL,
    nco_code character varying(32) NOT NULL,
    ordinal integer NOT NULL
);


--
-- Name: qp_skills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qp_skills (
    id uuid NOT NULL,
    qp_id uuid NOT NULL,
    skill_id uuid NOT NULL,
    requirement character varying NOT NULL,
    group_name character varying,
    nsqf_level numeric(3,1),
    weightage numeric(5,2),
    total_marks integer,
    CONSTRAINT ck_qp_skill_requirement CHECK (((requirement)::text = ANY ((ARRAY['compulsory'::character varying, 'elective'::character varying, 'optional'::character varying])::text[])))
);


--
-- Name: qualification_packs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.qualification_packs (
    id uuid NOT NULL,
    qp_code character varying NOT NULL,
    version character varying NOT NULL,
    slug character varying NOT NULL,
    name_en character varying NOT NULL,
    name_hi character varying,
    job_role_en character varying,
    job_role_hi character varying,
    nsqf_level numeric(3,1),
    status character varying,
    total_hours integer,
    is_current boolean NOT NULL,
    sector_id uuid,
    sub_sector_id uuid,
    occupation_id uuid,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    awarding_body_id uuid,
    total_marks integer,
    min_pass_percent numeric(5,2),
    credits numeric(6,2),
    CONSTRAINT ck_qp_nsqf_level CHECK (((nsqf_level IS NULL) OR ((nsqf_level >= (1)::numeric) AND (nsqf_level <= (10)::numeric))))
);


--
-- Name: sectors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sectors (
    id uuid NOT NULL,
    sector_ref character varying NOT NULL,
    name_en character varying NOT NULL,
    name_hi character varying,
    slug character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    sector_code character varying(32),
    logo_url character varying(1024),
    awarding_body_id uuid
);


--
-- Name: skill_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skill_aliases (
    id uuid NOT NULL,
    skill_id uuid NOT NULL,
    surface_form character varying NOT NULL,
    script character varying NOT NULL,
    CONSTRAINT ck_alias_script CHECK (((script)::text = ANY ((ARRAY['latin'::character varying, 'devanagari'::character varying, 'transliteration'::character varying])::text[])))
);


--
-- Name: skill_concepts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skill_concepts (
    id uuid NOT NULL,
    slug character varying(280) NOT NULL,
    normalised_name text NOT NULL,
    name_en text NOT NULL,
    name_hi text,
    awarding_body_id uuid,
    nsqf_level numeric(3,1),
    canonical_skill_id uuid,
    member_count integer DEFAULT 1 NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: skill_generic_criteria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skill_generic_criteria (
    id uuid NOT NULL,
    skill_id uuid NOT NULL,
    ordinal integer NOT NULL,
    gs_ref character varying(32),
    text_en text NOT NULL,
    text_hi text
);


--
-- Name: skill_knowledge_params; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skill_knowledge_params (
    id uuid NOT NULL,
    skill_id uuid NOT NULL,
    ordinal integer NOT NULL,
    kp_ref character varying(32),
    text_en text NOT NULL,
    text_hi text
);


--
-- Name: skill_performance_criteria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skill_performance_criteria (
    id uuid NOT NULL,
    element_id uuid NOT NULL,
    ordinal integer NOT NULL,
    pc_ref character varying(32),
    description_en text NOT NULL,
    description_hi text,
    theory_marks numeric(8,2),
    practical_marks numeric(8,2),
    viva_marks numeric(8,2),
    ojt_marks numeric(8,2),
    total_marks numeric(8,2)
);


--
-- Name: skill_performance_elements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skill_performance_elements (
    id uuid NOT NULL,
    skill_id uuid NOT NULL,
    ordinal integer NOT NULL,
    name_en text NOT NULL,
    name_hi text,
    theory_marks numeric(8,2),
    practical_marks numeric(8,2),
    viva_marks numeric(8,2),
    ojt_marks numeric(8,2),
    total_marks numeric(8,2)
);


--
-- Name: skills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skills (
    id uuid NOT NULL,
    slug character varying NOT NULL,
    name_en character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    name_hi character varying,
    description_en character varying,
    description_hi character varying,
    skill_type character varying DEFAULT 'technical'::character varying NOT NULL,
    nsqf_level numeric(3,1),
    search_vector tsvector GENERATED ALWAYS AS ((((setweight(to_tsvector('english'::regconfig, (COALESCE(name_en, ''::character varying))::text), 'A'::"char") || setweight(to_tsvector('simple'::regconfig, (COALESCE(name_hi, ''::character varying))::text), 'A'::"char")) || setweight(to_tsvector('english'::regconfig, (COALESCE(description_en, ''::character varying))::text), 'C'::"char")) || setweight(to_tsvector('simple'::regconfig, (COALESCE(description_hi, ''::character varying))::text), 'C'::"char"))) STORED,
    nos_code character varying,
    nos_version character varying,
    nos_type character varying,
    source character varying DEFAULT 'curated'::character varying NOT NULL,
    qp_count integer DEFAULT 0 NOT NULL,
    sector_id uuid,
    occupation_id uuid,
    awarding_body_id uuid,
    concept_id uuid,
    CONSTRAINT ck_skills_nsqf_level CHECK (((nsqf_level IS NULL) OR ((nsqf_level >= (1)::numeric) AND (nsqf_level <= (10)::numeric)))),
    CONSTRAINT ck_skills_source CHECK (((source)::text = ANY ((ARRAY['nsqf'::character varying, 'curated'::character varying, 'legacy'::character varying])::text[]))),
    CONSTRAINT ck_skills_type CHECK (((skill_type)::text = ANY ((ARRAY['technical'::character varying, 'core'::character varying, 'generic'::character varying])::text[])))
);


--
-- Name: states; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.states (
    id uuid NOT NULL,
    state_code integer NOT NULL,
    name character varying(160) NOT NULL,
    slug character varying(160) NOT NULL,
    ncvet_code character varying(32),
    status character varying(32)
);


--
-- Name: sub_districts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sub_districts (
    id uuid NOT NULL,
    district_id uuid NOT NULL,
    code integer,
    name character varying(160) NOT NULL
);


--
-- Name: sub_sectors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sub_sectors (
    id uuid NOT NULL,
    sector_id uuid NOT NULL,
    sub_sector_ref character varying NOT NULL,
    name_en character varying NOT NULL,
    name_hi character varying
);


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tenants (
    id uuid NOT NULL,
    slug character varying NOT NULL,
    name character varying NOT NULL,
    tenant_type character varying NOT NULL,
    city character varying,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    description text,
    website text,
    logo_url text,
    contact_email text,
    is_verified boolean DEFAULT false NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_tenants_type CHECK (((tenant_type)::text = ANY ((ARRAY['employer'::character varying, 'course_provider'::character varying, 'personal'::character varying])::text[])))
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    phone character varying,
    email character varying,
    full_name character varying,
    phone_verified_at timestamp with time zone,
    email_verified_at timestamp with time zone,
    is_active boolean NOT NULL,
    preferred_locale character varying NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_users_has_identifier CHECK (((phone IS NOT NULL) OR (email IS NOT NULL)))
);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: analytics_events analytics_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analytics_events
    ADD CONSTRAINT analytics_events_pkey PRIMARY KEY (id);


--
-- Name: awarding_bodies awarding_bodies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.awarding_bodies
    ADD CONSTRAINT awarding_bodies_pkey PRIMARY KEY (id);


--
-- Name: candidate_certifications candidate_certifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_certifications
    ADD CONSTRAINT candidate_certifications_pkey PRIMARY KEY (id);


--
-- Name: candidate_educations candidate_educations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_educations
    ADD CONSTRAINT candidate_educations_pkey PRIMARY KEY (id);


--
-- Name: candidate_experiences candidate_experiences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_experiences
    ADD CONSTRAINT candidate_experiences_pkey PRIMARY KEY (id);


--
-- Name: candidate_languages candidate_languages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_languages
    ADD CONSTRAINT candidate_languages_pkey PRIMARY KEY (id);


--
-- Name: candidate_preferred_locations candidate_preferred_locations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_preferred_locations
    ADD CONSTRAINT candidate_preferred_locations_pkey PRIMARY KEY (id);


--
-- Name: candidate_preferred_roles candidate_preferred_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_preferred_roles
    ADD CONSTRAINT candidate_preferred_roles_pkey PRIMARY KEY (id);


--
-- Name: candidate_profiles candidate_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_profiles
    ADD CONSTRAINT candidate_profiles_pkey PRIMARY KEY (id);


--
-- Name: candidate_skills candidate_skills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_skills
    ADD CONSTRAINT candidate_skills_pkey PRIMARY KEY (id);


--
-- Name: course_skills course_skills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_skills
    ADD CONSTRAINT course_skills_pkey PRIMARY KEY (id);


--
-- Name: courses courses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_pkey PRIMARY KEY (id);


--
-- Name: districts districts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.districts
    ADD CONSTRAINT districts_pkey PRIMARY KEY (id);


--
-- Name: job_skills job_skills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_skills
    ADD CONSTRAINT job_skills_pkey PRIMARY KEY (id);


--
-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);


--
-- Name: memberships memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_pkey PRIMARY KEY (id);


--
-- Name: model_curricula model_curricula_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_curricula
    ADD CONSTRAINT model_curricula_pkey PRIMARY KEY (id);


--
-- Name: occupations occupations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.occupations
    ADD CONSTRAINT occupations_pkey PRIMARY KEY (id);


--
-- Name: qp_entry_routes qp_entry_routes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qp_entry_routes
    ADD CONSTRAINT qp_entry_routes_pkey PRIMARY KEY (id);


--
-- Name: qp_nco_codes qp_nco_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qp_nco_codes
    ADD CONSTRAINT qp_nco_codes_pkey PRIMARY KEY (id);


--
-- Name: qp_skills qp_skills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qp_skills
    ADD CONSTRAINT qp_skills_pkey PRIMARY KEY (id);


--
-- Name: qualification_packs qualification_packs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qualification_packs
    ADD CONSTRAINT qualification_packs_pkey PRIMARY KEY (id);


--
-- Name: sectors sectors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors
    ADD CONSTRAINT sectors_pkey PRIMARY KEY (id);


--
-- Name: skill_aliases skill_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_aliases
    ADD CONSTRAINT skill_aliases_pkey PRIMARY KEY (id);


--
-- Name: skill_concepts skill_concepts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_concepts
    ADD CONSTRAINT skill_concepts_pkey PRIMARY KEY (id);


--
-- Name: skill_generic_criteria skill_generic_criteria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_generic_criteria
    ADD CONSTRAINT skill_generic_criteria_pkey PRIMARY KEY (id);


--
-- Name: skill_knowledge_params skill_knowledge_params_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_knowledge_params
    ADD CONSTRAINT skill_knowledge_params_pkey PRIMARY KEY (id);


--
-- Name: skill_performance_criteria skill_performance_criteria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_performance_criteria
    ADD CONSTRAINT skill_performance_criteria_pkey PRIMARY KEY (id);


--
-- Name: skill_performance_elements skill_performance_elements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_performance_elements
    ADD CONSTRAINT skill_performance_elements_pkey PRIMARY KEY (id);


--
-- Name: skills skills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skills
    ADD CONSTRAINT skills_pkey PRIMARY KEY (id);


--
-- Name: states states_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.states
    ADD CONSTRAINT states_pkey PRIMARY KEY (id);


--
-- Name: sub_districts sub_districts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sub_districts
    ADD CONSTRAINT sub_districts_pkey PRIMARY KEY (id);


--
-- Name: sub_sectors sub_sectors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sub_sectors
    ADD CONSTRAINT sub_sectors_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: skill_aliases uq_alias_skill_form; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_aliases
    ADD CONSTRAINT uq_alias_skill_form UNIQUE (skill_id, surface_form);


--
-- Name: candidate_languages uq_candidate_language; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_languages
    ADD CONSTRAINT uq_candidate_language UNIQUE (profile_id, language);


--
-- Name: candidate_preferred_locations uq_candidate_preferred_location; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_preferred_locations
    ADD CONSTRAINT uq_candidate_preferred_location UNIQUE (profile_id, state, district);


--
-- Name: candidate_preferred_roles uq_candidate_preferred_role; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_preferred_roles
    ADD CONSTRAINT uq_candidate_preferred_role UNIQUE (profile_id, title);


--
-- Name: candidate_skills uq_candidate_skill; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_skills
    ADD CONSTRAINT uq_candidate_skill UNIQUE (profile_id, skill_id);


--
-- Name: course_skills uq_course_skill; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_skills
    ADD CONSTRAINT uq_course_skill UNIQUE (course_id, skill_id);


--
-- Name: skill_generic_criteria uq_generic_criterion_ordinal; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_generic_criteria
    ADD CONSTRAINT uq_generic_criterion_ordinal UNIQUE (skill_id, ordinal);


--
-- Name: job_skills uq_job_skill; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_skills
    ADD CONSTRAINT uq_job_skill UNIQUE (job_id, skill_id);


--
-- Name: skill_knowledge_params uq_knowledge_param_ordinal; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_knowledge_params
    ADD CONSTRAINT uq_knowledge_param_ordinal UNIQUE (skill_id, ordinal);


--
-- Name: model_curricula uq_mc_code_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_curricula
    ADD CONSTRAINT uq_mc_code_version UNIQUE (qp_code, mc_version);


--
-- Name: memberships uq_membership_user_tenant; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT uq_membership_user_tenant UNIQUE (user_id, tenant_id);


--
-- Name: occupations uq_occupation_sector_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.occupations
    ADD CONSTRAINT uq_occupation_sector_ref UNIQUE (sector_id, occupation_ref);


--
-- Name: skill_performance_criteria uq_performance_criterion_ordinal; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_performance_criteria
    ADD CONSTRAINT uq_performance_criterion_ordinal UNIQUE (element_id, ordinal);


--
-- Name: skill_performance_elements uq_performance_element_ordinal; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_performance_elements
    ADD CONSTRAINT uq_performance_element_ordinal UNIQUE (skill_id, ordinal);


--
-- Name: qualification_packs uq_qp_code_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qualification_packs
    ADD CONSTRAINT uq_qp_code_version UNIQUE (qp_code, version);


--
-- Name: qp_entry_routes uq_qp_entry_route_ordinal; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qp_entry_routes
    ADD CONSTRAINT uq_qp_entry_route_ordinal UNIQUE (qp_id, ordinal);


--
-- Name: qp_nco_codes uq_qp_nco_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qp_nco_codes
    ADD CONSTRAINT uq_qp_nco_code UNIQUE (qp_id, nco_code);


--
-- Name: qp_skills uq_qp_skill; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qp_skills
    ADD CONSTRAINT uq_qp_skill UNIQUE (qp_id, skill_id);


--
-- Name: skill_concepts uq_skill_concept_identity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_concepts
    ADD CONSTRAINT uq_skill_concept_identity UNIQUE (awarding_body_id, normalised_name, nsqf_level);


--
-- Name: sub_districts uq_sub_district_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sub_districts
    ADD CONSTRAINT uq_sub_district_name UNIQUE (district_id, name);


--
-- Name: sub_sectors uq_sub_sector_ref; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sub_sectors
    ADD CONSTRAINT uq_sub_sector_ref UNIQUE (sector_id, sub_sector_ref);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_analytics_events_name_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_name_time ON public.analytics_events USING btree (name, occurred_at);


--
-- Name: ix_analytics_events_occurred_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_occurred_at ON public.analytics_events USING btree (occurred_at);


--
-- Name: ix_analytics_events_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_user ON public.analytics_events USING btree (user_id);


--
-- Name: ix_awarding_bodies_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_awarding_bodies_code ON public.awarding_bodies USING btree (code);


--
-- Name: ix_awarding_bodies_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_awarding_bodies_slug ON public.awarding_bodies USING btree (slug);


--
-- Name: ix_candidate_certifications_profile_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_certifications_profile_id ON public.candidate_certifications USING btree (profile_id);


--
-- Name: ix_candidate_educations_profile_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_educations_profile_id ON public.candidate_educations USING btree (profile_id);


--
-- Name: ix_candidate_experiences_profile_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_experiences_profile_id ON public.candidate_experiences USING btree (profile_id);


--
-- Name: ix_candidate_languages_profile_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_languages_profile_id ON public.candidate_languages USING btree (profile_id);


--
-- Name: ix_candidate_preferred_locations_district_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_preferred_locations_district_id ON public.candidate_preferred_locations USING btree (district_id);


--
-- Name: ix_candidate_preferred_locations_profile_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_preferred_locations_profile_id ON public.candidate_preferred_locations USING btree (profile_id);


--
-- Name: ix_candidate_preferred_locations_state_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_preferred_locations_state_id ON public.candidate_preferred_locations USING btree (state_id);


--
-- Name: ix_candidate_preferred_roles_profile_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_preferred_roles_profile_id ON public.candidate_preferred_roles USING btree (profile_id);


--
-- Name: ix_candidate_profiles_district_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_profiles_district_id ON public.candidate_profiles USING btree (district_id);


--
-- Name: ix_candidate_profiles_state_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_profiles_state_id ON public.candidate_profiles USING btree (state_id);


--
-- Name: ix_candidate_profiles_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_candidate_profiles_user_id ON public.candidate_profiles USING btree (user_id);


--
-- Name: ix_candidate_skills_skill_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_candidate_skills_skill_id ON public.candidate_skills USING btree (skill_id);


--
-- Name: ix_course_skills_skill_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_course_skills_skill_id ON public.course_skills USING btree (skill_id);


--
-- Name: ix_courses_search_vector; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_search_vector ON public.courses USING gin (search_vector);


--
-- Name: ix_courses_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_courses_slug ON public.courses USING btree (slug);


--
-- Name: ix_courses_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_status ON public.courses USING btree (status);


--
-- Name: ix_courses_status_language; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_status_language ON public.courses USING btree (status, language);


--
-- Name: ix_courses_status_mode; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_status_mode ON public.courses USING btree (status, mode);


--
-- Name: ix_courses_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_courses_tenant_id ON public.courses USING btree (tenant_id);


--
-- Name: ix_districts_district_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_districts_district_code ON public.districts USING btree (district_code);


--
-- Name: ix_districts_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_districts_slug ON public.districts USING btree (slug);


--
-- Name: ix_districts_state_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_districts_state_id ON public.districts USING btree (state_id);


--
-- Name: ix_generic_criteria_skill_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_generic_criteria_skill_id ON public.skill_generic_criteria USING btree (skill_id);


--
-- Name: ix_job_skills_skill_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_job_skills_skill_id ON public.job_skills USING btree (skill_id);


--
-- Name: ix_jobs_district_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_district_id ON public.jobs USING btree (district_id);


--
-- Name: ix_jobs_search_vector; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_search_vector ON public.jobs USING gin (search_vector);


--
-- Name: ix_jobs_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_jobs_slug ON public.jobs USING btree (slug);


--
-- Name: ix_jobs_state_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_state_id ON public.jobs USING btree (state_id);


--
-- Name: ix_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_status ON public.jobs USING btree (status);


--
-- Name: ix_jobs_status_employment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_status_employment ON public.jobs USING btree (status, employment_type);


--
-- Name: ix_jobs_status_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_status_state ON public.jobs USING btree (status, location_state);


--
-- Name: ix_jobs_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_jobs_tenant_id ON public.jobs USING btree (tenant_id);


--
-- Name: ix_knowledge_params_skill_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_knowledge_params_skill_id ON public.skill_knowledge_params USING btree (skill_id);


--
-- Name: ix_memberships_tenant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_memberships_tenant_id ON public.memberships USING btree (tenant_id);


--
-- Name: ix_memberships_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_memberships_user_id ON public.memberships USING btree (user_id);


--
-- Name: ix_model_curricula_qp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_model_curricula_qp_code ON public.model_curricula USING btree (qp_code);


--
-- Name: ix_model_curricula_qp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_model_curricula_qp_id ON public.model_curricula USING btree (qp_id);


--
-- Name: ix_occupations_occupation_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_occupations_occupation_ref ON public.occupations USING btree (occupation_ref);


--
-- Name: ix_occupations_sector_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_occupations_sector_id ON public.occupations USING btree (sector_id);


--
-- Name: ix_performance_criteria_element_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_criteria_element_id ON public.skill_performance_criteria USING btree (element_id);


--
-- Name: ix_performance_elements_skill_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_elements_skill_id ON public.skill_performance_elements USING btree (skill_id);


--
-- Name: ix_qp_current_level; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qp_current_level ON public.qualification_packs USING btree (is_current, nsqf_level);


--
-- Name: ix_qp_entry_routes_qp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qp_entry_routes_qp_id ON public.qp_entry_routes USING btree (qp_id);


--
-- Name: ix_qp_nco_codes_nco_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qp_nco_codes_nco_code ON public.qp_nco_codes USING btree (nco_code);


--
-- Name: ix_qp_sector_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qp_sector_id ON public.qualification_packs USING btree (sector_id);


--
-- Name: ix_qp_skills_qp_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qp_skills_qp_id ON public.qp_skills USING btree (qp_id);


--
-- Name: ix_qp_skills_skill_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qp_skills_skill_id ON public.qp_skills USING btree (skill_id);


--
-- Name: ix_qualification_packs_awarding_body_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qualification_packs_awarding_body_id ON public.qualification_packs USING btree (awarding_body_id);


--
-- Name: ix_qualification_packs_occupation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qualification_packs_occupation_id ON public.qualification_packs USING btree (occupation_id);


--
-- Name: ix_qualification_packs_qp_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_qualification_packs_qp_code ON public.qualification_packs USING btree (qp_code);


--
-- Name: ix_qualification_packs_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_qualification_packs_slug ON public.qualification_packs USING btree (slug);


--
-- Name: ix_sectors_awarding_body_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sectors_awarding_body_id ON public.sectors USING btree (awarding_body_id);


--
-- Name: ix_sectors_sector_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sectors_sector_code ON public.sectors USING btree (sector_code);


--
-- Name: ix_sectors_sector_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_sectors_sector_ref ON public.sectors USING btree (sector_ref);


--
-- Name: ix_sectors_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_sectors_slug ON public.sectors USING btree (slug);


--
-- Name: ix_skill_aliases_form_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skill_aliases_form_trgm ON public.skill_aliases USING gin (lower((surface_form)::text) public.gin_trgm_ops);


--
-- Name: ix_skill_aliases_skill_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skill_aliases_skill_id ON public.skill_aliases USING btree (skill_id);


--
-- Name: ix_skill_concepts_body; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skill_concepts_body ON public.skill_concepts USING btree (awarding_body_id);


--
-- Name: ix_skill_concepts_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_skill_concepts_slug ON public.skill_concepts USING btree (slug);


--
-- Name: ix_skills_awarding_body_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skills_awarding_body_id ON public.skills USING btree (awarding_body_id);


--
-- Name: ix_skills_concept_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skills_concept_id ON public.skills USING btree (concept_id);


--
-- Name: ix_skills_name_en_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skills_name_en_trgm ON public.skills USING gin (lower((name_en)::text) public.gin_trgm_ops);


--
-- Name: ix_skills_nos_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_skills_nos_code ON public.skills USING btree (nos_code);


--
-- Name: ix_skills_occupation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skills_occupation_id ON public.skills USING btree (occupation_id);


--
-- Name: ix_skills_qp_count; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skills_qp_count ON public.skills USING btree (qp_count);


--
-- Name: ix_skills_search_vector; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skills_search_vector ON public.skills USING gin (search_vector);


--
-- Name: ix_skills_sector_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skills_sector_id ON public.skills USING btree (sector_id);


--
-- Name: ix_skills_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_skills_slug ON public.skills USING btree (slug);


--
-- Name: ix_skills_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skills_source ON public.skills USING btree (source);


--
-- Name: ix_skills_type_level; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_skills_type_level ON public.skills USING btree (skill_type, nsqf_level);


--
-- Name: ix_states_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_states_slug ON public.states USING btree (slug);


--
-- Name: ix_states_state_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_states_state_code ON public.states USING btree (state_code);


--
-- Name: ix_sub_districts_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sub_districts_code ON public.sub_districts USING btree (code);


--
-- Name: ix_sub_districts_district_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sub_districts_district_id ON public.sub_districts USING btree (district_id);


--
-- Name: ix_sub_sectors_sector_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sub_sectors_sector_id ON public.sub_sectors USING btree (sector_id);


--
-- Name: ix_tenants_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_tenants_slug ON public.tenants USING btree (slug);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_phone; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_phone ON public.users USING btree (phone);


--
-- Name: analytics_events analytics_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analytics_events
    ADD CONSTRAINT analytics_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: candidate_certifications candidate_certifications_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_certifications
    ADD CONSTRAINT candidate_certifications_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.candidate_profiles(id) ON DELETE CASCADE;


--
-- Name: candidate_certifications candidate_certifications_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_certifications
    ADD CONSTRAINT candidate_certifications_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE SET NULL;


--
-- Name: candidate_educations candidate_educations_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_educations
    ADD CONSTRAINT candidate_educations_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.candidate_profiles(id) ON DELETE CASCADE;


--
-- Name: candidate_experiences candidate_experiences_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_experiences
    ADD CONSTRAINT candidate_experiences_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.candidate_profiles(id) ON DELETE CASCADE;


--
-- Name: candidate_languages candidate_languages_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_languages
    ADD CONSTRAINT candidate_languages_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.candidate_profiles(id) ON DELETE CASCADE;


--
-- Name: candidate_preferred_locations candidate_preferred_locations_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_preferred_locations
    ADD CONSTRAINT candidate_preferred_locations_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.candidate_profiles(id) ON DELETE CASCADE;


--
-- Name: candidate_preferred_roles candidate_preferred_roles_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_preferred_roles
    ADD CONSTRAINT candidate_preferred_roles_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.candidate_profiles(id) ON DELETE CASCADE;


--
-- Name: candidate_profiles candidate_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_profiles
    ADD CONSTRAINT candidate_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: candidate_skills candidate_skills_profile_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_skills
    ADD CONSTRAINT candidate_skills_profile_id_fkey FOREIGN KEY (profile_id) REFERENCES public.candidate_profiles(id) ON DELETE CASCADE;


--
-- Name: candidate_skills candidate_skills_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_skills
    ADD CONSTRAINT candidate_skills_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE CASCADE;


--
-- Name: course_skills course_skills_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_skills
    ADD CONSTRAINT course_skills_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.courses(id) ON DELETE CASCADE;


--
-- Name: course_skills course_skills_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course_skills
    ADD CONSTRAINT course_skills_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE CASCADE;


--
-- Name: courses courses_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.courses
    ADD CONSTRAINT courses_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: districts districts_state_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.districts
    ADD CONSTRAINT districts_state_id_fkey FOREIGN KEY (state_id) REFERENCES public.states(id) ON DELETE CASCADE;


--
-- Name: candidate_preferred_locations fk_candidate_preferred_locations_district_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_preferred_locations
    ADD CONSTRAINT fk_candidate_preferred_locations_district_id FOREIGN KEY (district_id) REFERENCES public.districts(id) ON DELETE SET NULL;


--
-- Name: candidate_preferred_locations fk_candidate_preferred_locations_state_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_preferred_locations
    ADD CONSTRAINT fk_candidate_preferred_locations_state_id FOREIGN KEY (state_id) REFERENCES public.states(id) ON DELETE SET NULL;


--
-- Name: candidate_profiles fk_candidate_profiles_district_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_profiles
    ADD CONSTRAINT fk_candidate_profiles_district_id FOREIGN KEY (district_id) REFERENCES public.districts(id) ON DELETE SET NULL;


--
-- Name: candidate_profiles fk_candidate_profiles_state_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candidate_profiles
    ADD CONSTRAINT fk_candidate_profiles_state_id FOREIGN KEY (state_id) REFERENCES public.states(id) ON DELETE SET NULL;


--
-- Name: jobs fk_jobs_district_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT fk_jobs_district_id FOREIGN KEY (district_id) REFERENCES public.districts(id) ON DELETE SET NULL;


--
-- Name: jobs fk_jobs_state_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT fk_jobs_state_id FOREIGN KEY (state_id) REFERENCES public.states(id) ON DELETE SET NULL;


--
-- Name: occupations fk_occupations_sector_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.occupations
    ADD CONSTRAINT fk_occupations_sector_id FOREIGN KEY (sector_id) REFERENCES public.sectors(id) ON DELETE CASCADE;


--
-- Name: qualification_packs fk_qualification_packs_awarding_body_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qualification_packs
    ADD CONSTRAINT fk_qualification_packs_awarding_body_id FOREIGN KEY (awarding_body_id) REFERENCES public.awarding_bodies(id) ON DELETE SET NULL;


--
-- Name: sectors fk_sectors_awarding_body_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors
    ADD CONSTRAINT fk_sectors_awarding_body_id FOREIGN KEY (awarding_body_id) REFERENCES public.awarding_bodies(id) ON DELETE SET NULL;


--
-- Name: skills fk_skills_awarding_body_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skills
    ADD CONSTRAINT fk_skills_awarding_body_id FOREIGN KEY (awarding_body_id) REFERENCES public.awarding_bodies(id) ON DELETE SET NULL;


--
-- Name: skills fk_skills_concept_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skills
    ADD CONSTRAINT fk_skills_concept_id FOREIGN KEY (concept_id) REFERENCES public.skill_concepts(id) ON DELETE SET NULL;


--
-- Name: skills fk_skills_occupation_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skills
    ADD CONSTRAINT fk_skills_occupation_id FOREIGN KEY (occupation_id) REFERENCES public.occupations(id) ON DELETE SET NULL;


--
-- Name: skills fk_skills_sector_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skills
    ADD CONSTRAINT fk_skills_sector_id FOREIGN KEY (sector_id) REFERENCES public.sectors(id) ON DELETE SET NULL;


--
-- Name: job_skills job_skills_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_skills
    ADD CONSTRAINT job_skills_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id) ON DELETE CASCADE;


--
-- Name: job_skills job_skills_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_skills
    ADD CONSTRAINT job_skills_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE CASCADE;


--
-- Name: jobs jobs_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: memberships memberships_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id) ON DELETE CASCADE;


--
-- Name: memberships memberships_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: model_curricula model_curricula_qp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.model_curricula
    ADD CONSTRAINT model_curricula_qp_id_fkey FOREIGN KEY (qp_id) REFERENCES public.qualification_packs(id) ON DELETE SET NULL;


--
-- Name: qp_entry_routes qp_entry_routes_qp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qp_entry_routes
    ADD CONSTRAINT qp_entry_routes_qp_id_fkey FOREIGN KEY (qp_id) REFERENCES public.qualification_packs(id) ON DELETE CASCADE;


--
-- Name: qp_nco_codes qp_nco_codes_qp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qp_nco_codes
    ADD CONSTRAINT qp_nco_codes_qp_id_fkey FOREIGN KEY (qp_id) REFERENCES public.qualification_packs(id) ON DELETE CASCADE;


--
-- Name: qp_skills qp_skills_qp_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qp_skills
    ADD CONSTRAINT qp_skills_qp_id_fkey FOREIGN KEY (qp_id) REFERENCES public.qualification_packs(id) ON DELETE CASCADE;


--
-- Name: qp_skills qp_skills_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qp_skills
    ADD CONSTRAINT qp_skills_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE CASCADE;


--
-- Name: qualification_packs qualification_packs_occupation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qualification_packs
    ADD CONSTRAINT qualification_packs_occupation_id_fkey FOREIGN KEY (occupation_id) REFERENCES public.occupations(id) ON DELETE SET NULL;


--
-- Name: qualification_packs qualification_packs_sector_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qualification_packs
    ADD CONSTRAINT qualification_packs_sector_id_fkey FOREIGN KEY (sector_id) REFERENCES public.sectors(id) ON DELETE SET NULL;


--
-- Name: qualification_packs qualification_packs_sub_sector_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.qualification_packs
    ADD CONSTRAINT qualification_packs_sub_sector_id_fkey FOREIGN KEY (sub_sector_id) REFERENCES public.sub_sectors(id) ON DELETE SET NULL;


--
-- Name: skill_aliases skill_aliases_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_aliases
    ADD CONSTRAINT skill_aliases_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE CASCADE;


--
-- Name: skill_concepts skill_concepts_awarding_body_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_concepts
    ADD CONSTRAINT skill_concepts_awarding_body_id_fkey FOREIGN KEY (awarding_body_id) REFERENCES public.awarding_bodies(id) ON DELETE CASCADE;


--
-- Name: skill_concepts skill_concepts_canonical_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_concepts
    ADD CONSTRAINT skill_concepts_canonical_skill_id_fkey FOREIGN KEY (canonical_skill_id) REFERENCES public.skills(id) ON DELETE SET NULL;


--
-- Name: skill_generic_criteria skill_generic_criteria_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_generic_criteria
    ADD CONSTRAINT skill_generic_criteria_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE CASCADE;


--
-- Name: skill_knowledge_params skill_knowledge_params_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_knowledge_params
    ADD CONSTRAINT skill_knowledge_params_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE CASCADE;


--
-- Name: skill_performance_criteria skill_performance_criteria_element_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_performance_criteria
    ADD CONSTRAINT skill_performance_criteria_element_id_fkey FOREIGN KEY (element_id) REFERENCES public.skill_performance_elements(id) ON DELETE CASCADE;


--
-- Name: skill_performance_elements skill_performance_elements_skill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skill_performance_elements
    ADD CONSTRAINT skill_performance_elements_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id) ON DELETE CASCADE;


--
-- Name: sub_districts sub_districts_district_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sub_districts
    ADD CONSTRAINT sub_districts_district_id_fkey FOREIGN KEY (district_id) REFERENCES public.districts(id) ON DELETE CASCADE;


--
-- Name: sub_sectors sub_sectors_sector_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sub_sectors
    ADD CONSTRAINT sub_sectors_sector_id_fkey FOREIGN KEY (sector_id) REFERENCES public.sectors(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict DoVRoHJzDILhvI2x0JB8dHF4yoW639oX8AoRfRtljTVMBG0Xcbx79g8jLvOe1Yx

