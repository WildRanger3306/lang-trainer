-- I1: словарь виден и фильтруется

SELECT count(*) AS entries FROM entries;
SELECT count(*) AS translations FROM entry_translations;
SELECT name, count(*) AS entries
FROM textbooks t
JOIN entry_textbooks et ON et.textbook_id = t.id
GROUP BY t.name
ORDER BY t.name;

SELECT language, count(*) FROM entries GROUP BY language ORDER BY 1;

SELECT e.form, e.part_of_speech, e.part_of_speech_code,
       string_agg(tr.text, ' | ' ORDER BY tr.position) AS translations,
       string_agg(tb.name, ', ') AS textbooks
FROM entries e
JOIN entry_translations tr ON tr.entry_id = e.id
LEFT JOIN entry_textbooks et ON et.entry_id = e.id
LEFT JOIN textbooks tb ON tb.id = et.textbook_id
WHERE e.language = 'en'
  AND e.part_of_speech = 'phrase'
GROUP BY e.id
ORDER BY e.form
LIMIT 8;

SELECT e.form, string_agg(tr.text, ' | ' ORDER BY tr.position) AS translations
FROM entries e
JOIN entry_translations tr ON tr.entry_id = e.id
GROUP BY e.id
HAVING count(tr.entry_id) > 1
ORDER BY e.form;
