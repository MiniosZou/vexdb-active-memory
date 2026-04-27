DROP TRIGGER IF EXISTS trg_memories_updated_at ON active_memory.memories;
CREATE TRIGGER trg_memories_updated_at
BEFORE UPDATE ON active_memory.memories
FOR EACH ROW
EXECUTE PROCEDURE active_memory.touch_updated_at();

DROP TRIGGER IF EXISTS trg_policies_updated_at ON active_memory.policies;
CREATE TRIGGER trg_policies_updated_at
BEFORE UPDATE ON active_memory.policies
FOR EACH ROW
EXECUTE PROCEDURE active_memory.touch_updated_at();
