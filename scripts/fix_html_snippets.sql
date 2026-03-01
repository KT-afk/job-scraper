-- Remove HTML tags from snippets
UPDATE jobposting
SET snippet = regexp_replace(
    regexp_replace(snippet, '<[^>]+>', ' ', 'g'),
    '\s+', ' ', 'g'
)
WHERE snippet ~ '<[a-zA-Z]';
