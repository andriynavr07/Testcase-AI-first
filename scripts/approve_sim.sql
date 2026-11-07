WITH a AS (
    UPDATE tickets SET status = 'approved'
    WHERE status = 'draft_ready' AND ticket_id LIKE 'SIM-%'
    RETURNING id
)
INSERT INTO outbound_replies (ticket_id, message)
SELECT a.id, (SELECT body FROM drafts d WHERE d.ticket_id = a.id ORDER BY d.id DESC LIMIT 1)
FROM a
ON CONFLICT (ticket_id) DO NOTHING;