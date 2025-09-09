--
-- PostgreSQL database dump
--

-- Dumped from database version 10.7
-- Dumped by pg_dump version 12.2

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

SET default_tablespace = '';


--
-- Name: transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transactions (
    transaction_date date,
    country_code text,
    grant_code text,
    budget_line_code text,
    account_code text,
    site_code text,
    sector_code text,
    transaction_code text,
    transaction_description text,
    currency_code character varying(4),
    budget_line_description text,
    amount numeric,
    dummy_field_1 text,
    dummy_field_2 text,
    dummy_field_3 text,
    dummy_field_4 text,
    dummy_field_5 text
);


--
-- Name: TABLE transactions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.transactions IS 'Created 2020-03-30T23:25:13.043842';



--
-- Data for Name: transactions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.transactions (transaction_date, country_code, grant_code, budget_line_code, account_code, site_code, sector_code, transaction_code, transaction_description, currency_code, budget_line_description, amount, dummy_field_1, dummy_field_2, dummy_field_3, dummy_field_4, dummy_field_5) FROM stdin;
2015-05-09	2LM	GH012	QRS56	34567	UV	WXYZ	9012345 dolorad	Quisul Nostrudlabo	USD	DCOP/ Snr. TA (Health)-SA	7890	\N	\N	\N	\N	\N
2015-05-09	2LM	GH012	WXY56	34567	UV	UVWX	9012345 dolorad	Ipsumc L. Ipsumc	USD	Senior Advisor (M&E)-SAL	8901	\N	\N	\N	\N	\N
2015-05-09	2LM	GH012	WXY90	23456	UV	UVWX	IPSU 56789	Eliteiusm + Elit elit	USD	Central-level Self-Assess	890	\N	\N	\N	\N	\N
2015-05-10	2HI	AB234	D4567	56789	\N	UVWX	1234	Dolorequ dolo Magnano Do.	USD	Housing - CO Support	7.89	\N	\N	\N	\N	\N
2015-05-10	7WX	AB234	GH45	90123	DEF	WXYZ	FG7890/7890	ALIQUI EXCONSE/AL EXCO	JOD	Finance Controller	567.8	\N	\N	\N	\N	\N
2015-05-10	7WX	AB234	HIJ67	1234	DEF	WXYZ	ELIT/6789	ALIQUAE ALIQU QUISULL	JOD	Deputy Director of Operat	4.56	\N	\N	\N	\N	\N
2015-05-10	7WX	AB234	WXY90	1234	DEF	WXYZ	IRU/9012	AMET CONSECTET/CONSEC.C	JOD	Field Coordinator Mafraq	6.78	\N	\N	\N	\N	\N
\.



--
-- PostgreSQL database dump complete
--

