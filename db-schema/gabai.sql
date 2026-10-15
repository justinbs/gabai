--
-- PostgreSQL database dump
--

\restrict 4BPhJjUQyTrhZTcL6O6EKpGpc9aHTvP4hFw7O3JK4pyW9wdxcLPa0ExPzfVihoc

-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15

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
-- Name: request_status; Type: TYPE; Schema: public; Owner: gabai
--

CREATE TYPE public.request_status AS ENUM (
    'submitted',
    'classified',
    'routed',
    'under_review',
    'in_progress',
    'resolved',
    'closed',
    'referred'
);


ALTER TYPE public.request_status OWNER TO gabai;

--
-- Name: role; Type: TYPE; Schema: public; Owner: gabai
--

CREATE TYPE public.role AS ENUM (
    'citizen',
    'staff',
    'admin'
);


ALTER TYPE public.role OWNER TO gabai;

--
-- Name: urgency; Type: TYPE; Schema: public; Owner: gabai
--

CREATE TYPE public.urgency AS ENUM (
    'low',
    'medium',
    'high'
);


ALTER TYPE public.urgency OWNER TO gabai;

--
-- Name: audit_log_entries_append_only(); Type: FUNCTION; Schema: public; Owner: gabai
--

CREATE FUNCTION public.audit_log_entries_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND NEW.ip_address IS NULL
       AND (NEW.id, NEW.actor_id, NEW.action, NEW.object_type, NEW.object_id,
            NEW.detail, NEW.created_at)
           IS NOT DISTINCT FROM
           (OLD.id, OLD.actor_id, OLD.action, OLD.object_type, OLD.object_id,
            OLD.detail, OLD.created_at)
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'audit_log_entries is append-only: % refused', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;


ALTER FUNCTION public.audit_log_entries_append_only() OWNER TO gabai;

--
-- Name: status_history_entries_append_only(); Type: FUNCTION; Schema: public; Owner: gabai
--

CREATE FUNCTION public.status_history_entries_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND (NEW.id, NEW.request_id, NEW.from_status, NEW.to_status,
            NEW.actor_id, NEW.created_at)
           IS NOT DISTINCT FROM
           (OLD.id, OLD.request_id, OLD.from_status, OLD.to_status,
            OLD.actor_id, OLD.created_at)
       AND (NEW.note IS NOT DISTINCT FROM OLD.note
            OR NEW.note IS NULL
            OR NEW.note = '[Removed after the retention period]')
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'status_history_entries is append-only: % refused', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;


ALTER FUNCTION public.status_history_entries_append_only() OWNER TO gabai;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO gabai;

--
-- Name: attachments; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.attachments (
    id integer NOT NULL,
    request_id integer NOT NULL,
    filename text NOT NULL,
    stored_path character varying(255) NOT NULL,
    mime_type character varying(100) NOT NULL,
    size_bytes integer NOT NULL,
    uploaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.attachments OWNER TO gabai;

--
-- Name: attachments_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.attachments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.attachments_id_seq OWNER TO gabai;

--
-- Name: attachments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.attachments_id_seq OWNED BY public.attachments.id;


--
-- Name: audit_log_entries; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.audit_log_entries (
    id integer NOT NULL,
    actor_id uuid,
    action character varying(100) NOT NULL,
    object_type character varying(50) NOT NULL,
    object_id character varying(100),
    detail jsonb,
    ip_address character varying(45),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.audit_log_entries OWNER TO gabai;

--
-- Name: audit_log_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.audit_log_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.audit_log_entries_id_seq OWNER TO gabai;

--
-- Name: audit_log_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.audit_log_entries_id_seq OWNED BY public.audit_log_entries.id;


--
-- Name: categories; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.categories (
    id integer NOT NULL,
    slug character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    description character varying(500),
    is_active boolean NOT NULL
);


ALTER TABLE public.categories OWNER TO gabai;

--
-- Name: categories_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.categories_id_seq OWNER TO gabai;

--
-- Name: categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.categories_id_seq OWNED BY public.categories.id;


--
-- Name: duplicate_suggestions; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.duplicate_suggestions (
    id integer NOT NULL,
    request_id integer NOT NULL,
    candidate_id integer NOT NULL,
    score double precision NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    decision character varying(10),
    decided_by uuid,
    decided_at timestamp with time zone,
    CONSTRAINT ck_duplicate_decision CHECK (((decision IS NULL) OR ((decision)::text = ANY ((ARRAY['linked'::character varying, 'dismissed'::character varying])::text[]))))
);


ALTER TABLE public.duplicate_suggestions OWNER TO gabai;

--
-- Name: duplicate_suggestions_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.duplicate_suggestions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.duplicate_suggestions_id_seq OWNER TO gabai;

--
-- Name: duplicate_suggestions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.duplicate_suggestions_id_seq OWNED BY public.duplicate_suggestions.id;


--
-- Name: locations; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.locations (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.locations OWNER TO gabai;

--
-- Name: locations_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.locations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.locations_id_seq OWNER TO gabai;

--
-- Name: locations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.locations_id_seq OWNED BY public.locations.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.notifications (
    id integer NOT NULL,
    user_id uuid NOT NULL,
    request_id integer,
    reference_number character varying(20),
    message text NOT NULL,
    is_read boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.notifications OWNER TO gabai;

--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notifications_id_seq OWNER TO gabai;

--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: referral_agencies; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.referral_agencies (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    phone character varying(50),
    hours character varying(100),
    website character varying(200),
    notes character varying(300),
    is_active boolean DEFAULT true NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.referral_agencies OWNER TO gabai;

--
-- Name: referral_agencies_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.referral_agencies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.referral_agencies_id_seq OWNER TO gabai;

--
-- Name: referral_agencies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.referral_agencies_id_seq OWNED BY public.referral_agencies.id;


--
-- Name: requests; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.requests (
    id integer NOT NULL,
    reference_number character varying(20) NOT NULL,
    citizen_id uuid NOT NULL,
    description text NOT NULL,
    predicted_category_id integer,
    predicted_urgency public.urgency,
    category_confidence double precision,
    urgency_confidence double precision,
    final_category_id integer,
    final_urgency public.urgency,
    status public.request_status NOT NULL,
    assigned_staff_id uuid,
    model_version character varying(100),
    classified_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    redacted_at timestamp with time zone,
    urgent_flagged_at timestamp with time zone,
    urgent_reason text,
    location_id integer,
    duplicate_of_id integer,
    referred_agency_id integer,
    referred_at timestamp with time zone,
    referral_note text,
    CONSTRAINT ck_requests_not_own_duplicate CHECK ((duplicate_of_id <> id)),
    CONSTRAINT ck_requests_referred_has_agency CHECK ((((status)::text <> 'referred'::text) OR (referred_agency_id IS NOT NULL)))
);


ALTER TABLE public.requests OWNER TO gabai;

--
-- Name: requests_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.requests_id_seq OWNER TO gabai;

--
-- Name: requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.requests_id_seq OWNED BY public.requests.id;


--
-- Name: routing_rules; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.routing_rules (
    id integer NOT NULL,
    category_id integer NOT NULL,
    staff_id uuid NOT NULL,
    is_active boolean NOT NULL
);


ALTER TABLE public.routing_rules OWNER TO gabai;

--
-- Name: routing_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.routing_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.routing_rules_id_seq OWNER TO gabai;

--
-- Name: routing_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.routing_rules_id_seq OWNED BY public.routing_rules.id;


--
-- Name: sign_in_failures; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.sign_in_failures (
    id integer NOT NULL,
    user_id uuid,
    ip_address character varying(45),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.sign_in_failures OWNER TO gabai;

--
-- Name: sign_in_failures_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.sign_in_failures_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sign_in_failures_id_seq OWNER TO gabai;

--
-- Name: sign_in_failures_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.sign_in_failures_id_seq OWNED BY public.sign_in_failures.id;


--
-- Name: site_settings; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.site_settings (
    id integer NOT NULL,
    barangay_name character varying(100) NOT NULL,
    place character varying(100) NOT NULL,
    address character varying(200),
    hotline character varying(50),
    office_hours character varying(100),
    theme character varying(10) DEFAULT 'green'::character varying NOT NULL,
    logo_path character varying(255),
    logo_version character varying(40),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_site_settings_single_row CHECK ((id = 1)),
    CONSTRAINT ck_site_settings_theme CHECK (((theme)::text = ANY ((ARRAY['green'::character varying, 'blue'::character varying, 'maroon'::character varying, 'teal'::character varying, 'purple'::character varying, 'brown'::character varying])::text[])))
);


ALTER TABLE public.site_settings OWNER TO gabai;

--
-- Name: site_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.site_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.site_settings_id_seq OWNER TO gabai;

--
-- Name: site_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.site_settings_id_seq OWNED BY public.site_settings.id;


--
-- Name: status_history_entries; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.status_history_entries (
    id integer NOT NULL,
    request_id integer NOT NULL,
    from_status public.request_status,
    to_status public.request_status NOT NULL,
    actor_id uuid,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.status_history_entries OWNER TO gabai;

--
-- Name: status_history_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: gabai
--

CREATE SEQUENCE public.status_history_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.status_history_entries_id_seq OWNER TO gabai;

--
-- Name: status_history_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: gabai
--

ALTER SEQUENCE public.status_history_entries_id_seq OWNED BY public.status_history_entries.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: gabai
--

CREATE TABLE public.users (
    full_name text NOT NULL,
    role public.role NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid NOT NULL,
    email character varying(320) NOT NULL,
    hashed_password character varying(1024) NOT NULL,
    is_active boolean NOT NULL,
    is_superuser boolean NOT NULL,
    is_verified boolean NOT NULL,
    must_change_password boolean DEFAULT false NOT NULL,
    approval_status character varying(10) DEFAULT 'pending'::character varying NOT NULL,
    residence text,
    deactivated_at timestamp with time zone,
    anonymized_at timestamp with time zone,
    terms_accepted_version character varying(20),
    terms_accepted_at timestamp with time zone,
    verification_method character varying(20),
    CONSTRAINT ck_users_approval_status CHECK (((approval_status)::text = ANY ((ARRAY['pending'::character varying, 'approved'::character varying, 'rejected'::character varying])::text[]))),
    CONSTRAINT ck_users_verification_method CHECK (((verification_method IS NULL) OR ((verification_method)::text = ANY ((ARRAY['id_in_person'::character varying, 'personally_known'::character varying, 'barangay_record'::character varying])::text[]))))
);


ALTER TABLE public.users OWNER TO gabai;

--
-- Name: attachments id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.attachments ALTER COLUMN id SET DEFAULT nextval('public.attachments_id_seq'::regclass);


--
-- Name: audit_log_entries id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.audit_log_entries ALTER COLUMN id SET DEFAULT nextval('public.audit_log_entries_id_seq'::regclass);


--
-- Name: categories id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.categories ALTER COLUMN id SET DEFAULT nextval('public.categories_id_seq'::regclass);


--
-- Name: duplicate_suggestions id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.duplicate_suggestions ALTER COLUMN id SET DEFAULT nextval('public.duplicate_suggestions_id_seq'::regclass);


--
-- Name: locations id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.locations ALTER COLUMN id SET DEFAULT nextval('public.locations_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: referral_agencies id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.referral_agencies ALTER COLUMN id SET DEFAULT nextval('public.referral_agencies_id_seq'::regclass);


--
-- Name: requests id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.requests ALTER COLUMN id SET DEFAULT nextval('public.requests_id_seq'::regclass);


--
-- Name: routing_rules id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.routing_rules ALTER COLUMN id SET DEFAULT nextval('public.routing_rules_id_seq'::regclass);


--
-- Name: sign_in_failures id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.sign_in_failures ALTER COLUMN id SET DEFAULT nextval('public.sign_in_failures_id_seq'::regclass);


--
-- Name: site_settings id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.site_settings ALTER COLUMN id SET DEFAULT nextval('public.site_settings_id_seq'::regclass);


--
-- Name: status_history_entries id; Type: DEFAULT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.status_history_entries ALTER COLUMN id SET DEFAULT nextval('public.status_history_entries_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: attachments attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_pkey PRIMARY KEY (id);


--
-- Name: audit_log_entries audit_log_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.audit_log_entries
    ADD CONSTRAINT audit_log_entries_pkey PRIMARY KEY (id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: categories categories_slug_key; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_slug_key UNIQUE (slug);


--
-- Name: duplicate_suggestions duplicate_suggestions_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.duplicate_suggestions
    ADD CONSTRAINT duplicate_suggestions_pkey PRIMARY KEY (id);


--
-- Name: locations locations_name_key; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_name_key UNIQUE (name);


--
-- Name: locations locations_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: referral_agencies referral_agencies_name_key; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.referral_agencies
    ADD CONSTRAINT referral_agencies_name_key UNIQUE (name);


--
-- Name: referral_agencies referral_agencies_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.referral_agencies
    ADD CONSTRAINT referral_agencies_pkey PRIMARY KEY (id);


--
-- Name: requests requests_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_pkey PRIMARY KEY (id);


--
-- Name: requests requests_reference_number_key; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_reference_number_key UNIQUE (reference_number);


--
-- Name: routing_rules routing_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.routing_rules
    ADD CONSTRAINT routing_rules_pkey PRIMARY KEY (id);


--
-- Name: sign_in_failures sign_in_failures_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.sign_in_failures
    ADD CONSTRAINT sign_in_failures_pkey PRIMARY KEY (id);


--
-- Name: site_settings site_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.site_settings
    ADD CONSTRAINT site_settings_pkey PRIMARY KEY (id);


--
-- Name: status_history_entries status_history_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.status_history_entries
    ADD CONSTRAINT status_history_entries_pkey PRIMARY KEY (id);


--
-- Name: duplicate_suggestions uq_duplicate_suggestion_pair; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.duplicate_suggestions
    ADD CONSTRAINT uq_duplicate_suggestion_pair UNIQUE (request_id, candidate_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_duplicate_suggestions_request_id; Type: INDEX; Schema: public; Owner: gabai
--

CREATE INDEX ix_duplicate_suggestions_request_id ON public.duplicate_suggestions USING btree (request_id);


--
-- Name: ix_requests_created_at; Type: INDEX; Schema: public; Owner: gabai
--

CREATE INDEX ix_requests_created_at ON public.requests USING btree (created_at);


--
-- Name: ix_requests_duplicate_of_id; Type: INDEX; Schema: public; Owner: gabai
--

CREATE INDEX ix_requests_duplicate_of_id ON public.requests USING btree (duplicate_of_id);


--
-- Name: ix_routing_rules_one_active_per_category; Type: INDEX; Schema: public; Owner: gabai
--

CREATE UNIQUE INDEX ix_routing_rules_one_active_per_category ON public.routing_rules USING btree (category_id) WHERE is_active;


--
-- Name: ix_sign_in_failures_ip_created; Type: INDEX; Schema: public; Owner: gabai
--

CREATE INDEX ix_sign_in_failures_ip_created ON public.sign_in_failures USING btree (ip_address, created_at);


--
-- Name: ix_sign_in_failures_user_created; Type: INDEX; Schema: public; Owner: gabai
--

CREATE INDEX ix_sign_in_failures_user_created ON public.sign_in_failures USING btree (user_id, created_at);


--
-- Name: ix_status_history_request_created; Type: INDEX; Schema: public; Owner: gabai
--

CREATE INDEX ix_status_history_request_created ON public.status_history_entries USING btree (request_id, created_at);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: gabai
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: audit_log_entries audit_log_entries_no_rewrite; Type: TRIGGER; Schema: public; Owner: gabai
--

CREATE TRIGGER audit_log_entries_no_rewrite BEFORE DELETE OR UPDATE ON public.audit_log_entries FOR EACH ROW EXECUTE FUNCTION public.audit_log_entries_append_only();


--
-- Name: audit_log_entries audit_log_entries_no_truncate; Type: TRIGGER; Schema: public; Owner: gabai
--

CREATE TRIGGER audit_log_entries_no_truncate BEFORE TRUNCATE ON public.audit_log_entries FOR EACH STATEMENT EXECUTE FUNCTION public.audit_log_entries_append_only();


--
-- Name: status_history_entries status_history_entries_no_rewrite; Type: TRIGGER; Schema: public; Owner: gabai
--

CREATE TRIGGER status_history_entries_no_rewrite BEFORE DELETE OR UPDATE ON public.status_history_entries FOR EACH ROW EXECUTE FUNCTION public.status_history_entries_append_only();


--
-- Name: status_history_entries status_history_entries_no_truncate; Type: TRIGGER; Schema: public; Owner: gabai
--

CREATE TRIGGER status_history_entries_no_truncate BEFORE TRUNCATE ON public.status_history_entries FOR EACH STATEMENT EXECUTE FUNCTION public.status_history_entries_append_only();


--
-- Name: attachments attachments_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.attachments
    ADD CONSTRAINT attachments_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.requests(id);


--
-- Name: audit_log_entries audit_log_entries_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.audit_log_entries
    ADD CONSTRAINT audit_log_entries_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id);


--
-- Name: duplicate_suggestions duplicate_suggestions_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.duplicate_suggestions
    ADD CONSTRAINT duplicate_suggestions_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.requests(id);


--
-- Name: duplicate_suggestions duplicate_suggestions_decided_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.duplicate_suggestions
    ADD CONSTRAINT duplicate_suggestions_decided_by_fkey FOREIGN KEY (decided_by) REFERENCES public.users(id);


--
-- Name: duplicate_suggestions duplicate_suggestions_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.duplicate_suggestions
    ADD CONSTRAINT duplicate_suggestions_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.requests(id);


--
-- Name: notifications notifications_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.requests(id);


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: requests requests_assigned_staff_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_assigned_staff_id_fkey FOREIGN KEY (assigned_staff_id) REFERENCES public.users(id);


--
-- Name: requests requests_citizen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_citizen_id_fkey FOREIGN KEY (citizen_id) REFERENCES public.users(id);


--
-- Name: requests requests_duplicate_of_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_duplicate_of_id_fkey FOREIGN KEY (duplicate_of_id) REFERENCES public.requests(id);


--
-- Name: requests requests_final_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_final_category_id_fkey FOREIGN KEY (final_category_id) REFERENCES public.categories(id);


--
-- Name: requests requests_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.locations(id);


--
-- Name: requests requests_predicted_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_predicted_category_id_fkey FOREIGN KEY (predicted_category_id) REFERENCES public.categories(id);


--
-- Name: requests requests_referred_agency_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.requests
    ADD CONSTRAINT requests_referred_agency_id_fkey FOREIGN KEY (referred_agency_id) REFERENCES public.referral_agencies(id);


--
-- Name: routing_rules routing_rules_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.routing_rules
    ADD CONSTRAINT routing_rules_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: routing_rules routing_rules_staff_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.routing_rules
    ADD CONSTRAINT routing_rules_staff_id_fkey FOREIGN KEY (staff_id) REFERENCES public.users(id);


--
-- Name: sign_in_failures sign_in_failures_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.sign_in_failures
    ADD CONSTRAINT sign_in_failures_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: status_history_entries status_history_entries_actor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.status_history_entries
    ADD CONSTRAINT status_history_entries_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id);


--
-- Name: status_history_entries status_history_entries_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: gabai
--

ALTER TABLE ONLY public.status_history_entries
    ADD CONSTRAINT status_history_entries_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.requests(id);


--
-- PostgreSQL database dump complete
--

\unrestrict 4BPhJjUQyTrhZTcL6O6EKpGpc9aHTvP4hFw7O3JK4pyW9wdxcLPa0ExPzfVihoc

