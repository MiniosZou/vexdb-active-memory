DO $$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS plpython3u;
        EXECUTE $fn$
        CREATE OR REPLACE FUNCTION active_memory.plpython_conflict_hint(
            p_old_content TEXT,
            p_candidate_content TEXT,
            p_distance DOUBLE PRECISION
        )
        RETURNS JSONB AS $py$
import json

decision = "append"
if p_distance is not None and p_distance < 0.08:
    decision = "update"

return json.dumps({
    "decision": decision,
    "rationale": "Local PL/Python hint only; production LLM adjudication should pass a reviewed decision to resolve_conflict.",
    "old_length": len(p_old_content or ""),
    "candidate_length": len(p_candidate_content or ""),
    "distance": p_distance,
})
$py$ LANGUAGE plpython3u;
        $fn$;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'PL/Python conflict hint is not available on this VexDB edition; resolve_conflict remains available.';
    END;
END;
$$;
