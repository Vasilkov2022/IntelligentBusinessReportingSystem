CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL,
    upload_time TIMESTAMP WITH TIME ZONE DEFAULT now(),
    status TEXT DEFAULT 'uploaded',
    analysis TEXT
);