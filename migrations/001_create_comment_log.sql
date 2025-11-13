-- Creates the SQLite schema required for the auto commenter bot.
CREATE TABLE IF NOT EXISTS comment_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_channel_id INTEGER NOT NULL,
    source_channel_username TEXT,
    send_as_channel_id INTEGER NOT NULL,
    send_as_username TEXT,
    post_id INTEGER NOT NULL,
    template_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);
