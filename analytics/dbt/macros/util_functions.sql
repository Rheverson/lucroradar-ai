{#
  Funções auxiliares de parsing seguro. Criadas em on-run-start para que a
  camada staging nunca falhe por um valor malformado: o valor vira NULL e o
  registro é enviado à quarentena com o motivo.
#}
{% macro create_util_functions() %}
CREATE SCHEMA IF NOT EXISTS util;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE OR REPLACE FUNCTION util.try_date(v text) RETURNS date
LANGUAGE plpgsql IMMUTABLE AS $fn$
BEGIN
    IF v IS NULL OR btrim(v) = '' THEN RETURN NULL; END IF;
    v := btrim(v);
    IF v ~ '^\d{4}-\d{2}-\d{2}$' THEN
        RETURN make_date(substr(v,1,4)::int, substr(v,6,2)::int, substr(v,9,2)::int);
    ELSIF v ~ '^\d{2}/\d{2}/\d{4}$' THEN
        RETURN make_date(substr(v,7,4)::int, substr(v,4,2)::int, substr(v,1,2)::int);
    END IF;
    RETURN NULL;
EXCEPTION WHEN others THEN
    RETURN NULL;
END;
$fn$;

CREATE OR REPLACE FUNCTION util.try_timestamp(v text) RETURNS timestamp
LANGUAGE plpgsql IMMUTABLE AS $fn$
BEGIN
    IF v IS NULL OR btrim(v) = '' THEN RETURN NULL; END IF;
    IF btrim(v) ~ '^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?$' THEN
        RETURN btrim(v)::timestamp;
    END IF;
    RETURN NULL;
EXCEPTION WHEN others THEN
    RETURN NULL;
END;
$fn$;

-- Aceita "1234.56" e o formato brasileiro "1.234,56"
CREATE OR REPLACE FUNCTION util.try_numeric(v text) RETURNS numeric
LANGUAGE plpgsql IMMUTABLE AS $fn$
BEGIN
    IF v IS NULL OR btrim(v) = '' THEN RETURN NULL; END IF;
    v := btrim(v);
    IF v ~ '^-?\d+(\.\d+)?$' THEN
        RETURN v::numeric;
    ELSIF v ~ '^-?\d{1,3}(\.\d{3})*(,\d+)?$' OR v ~ '^-?\d+,\d+$' THEN
        RETURN replace(replace(v, '.', ''), ',', '.')::numeric;
    END IF;
    RETURN NULL;
EXCEPTION WHEN others THEN
    RETURN NULL;
END;
$fn$;

CREATE OR REPLACE FUNCTION util.is_br_number(v text) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $fn$
    SELECT coalesce(btrim(v) ~ ',\d+$', false)
$fn$;

-- Nome limpo para exibição: sem espaços duplicados nas pontas/meio
CREATE OR REPLACE FUNCTION util.clean_name(v text) RETURNS text
LANGUAGE sql IMMUTABLE AS $fn$
    SELECT nullif(regexp_replace(btrim(v), '\s+', ' ', 'g'), '')
$fn$;

-- Chave de comparação de razão social: sem acento, maiúscula, abreviações
-- expandidas e sem sufixo societário. Usada APENAS para sugerir candidatos.
CREATE OR REPLACE FUNCTION util.company_key(v text) RETURNS text
LANGUAGE plpgsql STABLE AS $fn$
DECLARE k text;
BEGIN
    k := upper(public.unaccent(coalesce(v, '')));
    k := regexp_replace(k, '[^A-Z0-9 ]', ' ', 'g');
    k := regexp_replace(k, '\mCONSTR\M', 'CONSTRUTORA', 'g');
    k := regexp_replace(k, '\mENG\M', 'ENGENHARIA', 'g');
    k := regexp_replace(k, '\mIND\M', 'INDUSTRIA', 'g');
    k := regexp_replace(k, '\mAGROPEC\M', 'AGROPECUARIA', 'g');
    k := regexp_replace(k, '\mSERV\M', 'SERVICOS', 'g');
    k := regexp_replace(k, '\mPROD\M', 'PRODUCOES', 'g');
    k := regexp_replace(k, '\mMETAL\M', 'METALURGICA', 'g');
    k := regexp_replace(k, '\m(LTDA|S A|SA|ME|EIRELI|EPP)\M', ' ', 'g');
    RETURN nullif(btrim(regexp_replace(k, '\s+', ' ', 'g')), '');
END;
$fn$;
{% endmacro %}
