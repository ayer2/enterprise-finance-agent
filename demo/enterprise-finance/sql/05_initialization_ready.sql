USE enterprise_demo;

CREATE TABLE demo_generation_ready (
    id TINYINT PRIMARY KEY,
    ready TINYINT NOT NULL,
    generated_seed BIGINT NOT NULL,
    CONSTRAINT ck_demo_generation_ready CHECK (ready = 1)
) COMMENT='Created only after every initialization script has completed';

INSERT INTO demo_generation_ready (id, ready, generated_seed)
VALUES (1, 1, 20260824);
