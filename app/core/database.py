import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from threading import Lock

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import settings

logger = logging.getLogger(__name__)

class PlanetScaleDB:
    def __init__(self):
        self._connection = None
        self._connection_time = None
        self._lock = Lock()
        self.config = settings.PLANETSCALE_CONNECTION_CONFIG
        self.connection_timeout = 30
        self.max_connection_age = 3600

    def _is_connection_alive(self):
        if self._connection is None:
            return False
        
        try:
            if not self._connection.open:
                return False
            
            self._connection.ping(reconnect=False)
            
            if self._connection_time:
                age = time.time() - self._connection_time
                if age > self.max_connection_age:
                    logger.info(f"Connection age ({age:.0f}s) exceeds max age, reconnecting")
                    return False
            
            return True
        except Exception as e:
            logger.debug(f"Connection health check failed: {type(e).__name__}: {e}")
            return False

    def _get_connection(self):
        if self._is_connection_alive():
            return self._connection
        
        with self._lock:
            if self._is_connection_alive():
                return self._connection
            
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    pass
                self._connection = None
            
            try:
                self._connection = pymysql.connect(
                    host=self.config["host"],
                    user=self.config["user"],
                    password=self.config["password"],
                    database=self.config["database"],
                    charset="utf8mb4",
                    cursorclass=DictCursor,
                    autocommit=False,
                    connect_timeout=self.connection_timeout,
                    read_timeout=self.connection_timeout,
                    write_timeout=self.connection_timeout,
                    ssl={"ssl":{}}
                )
                self._connection_time = time.time()
                logger.debug("Connected to PlanetScale database")
            except Exception as e:
                logger.error(f"Failed to connect to PlanetScale: {e}")
                self._connection = None
                raise
        
        return self._connection

    def close(self):
        if self._connection:
            try:
                self._connection.close()
                logger.info("Closed PlanetScale database connection")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
            finally:
                self._connection = None

    def execute_query(self, sql: str, params: tuple = None, retries: int = 2) -> List[Dict]:
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    cursor.execute(sql, params or ())
                    return cursor.fetchall()
            except (pymysql.err.OperationalError, pymysql.err.DatabaseError, AttributeError) as e:
                last_error = e
                if attempt < retries:
                    self._connection = None
                    backoff = 0.5 * (2 ** attempt)
                    logger.warning(f"Database error (attempt {attempt + 1}/{retries + 1}), retrying in {backoff:.1f}s")
                    time.sleep(backoff)
                else:
                    logger.error(f"Query failed after {retries + 1} attempts: {e}")
            except Exception as e:
                logger.error(f"Query execution error: {e}")
                raise
        
        raise last_error if last_error else RuntimeError("Query execution failed")

    def execute_update(self, sql: str, params: tuple = None, retries: int = 2) -> int:
        last_error = None
        
        for attempt in range(retries + 1):
            conn = None
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    cursor.execute(sql, params or ())
                    conn.commit()
                    return cursor.rowcount
            except (pymysql.err.OperationalError, pymysql.err.DatabaseError, AttributeError) as e:
                last_error = e
                is_duplicate_column = "Duplicate column name" in str(e) or "1060" in str(e)
                
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                
                if attempt < retries:
                    self._connection = None
                    backoff = 0.5 * (2 ** attempt)
                    if not is_duplicate_column:
                        logger.warning(f"Database error (attempt {attempt + 1}/{retries + 1}), retrying in {backoff:.1f}s")
                    time.sleep(backoff)
                else:
                    if not is_duplicate_column:
                        logger.error(f"Update failed after {retries + 1} attempts: {e}")
            except Exception as e:
                is_duplicate_column = "Duplicate column name" in str(e) or "1060" in str(e)
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                if not is_duplicate_column:
                    logger.error(f"Update execution error: {e}")
                raise
        
        raise last_error if last_error else RuntimeError("Update execution failed")

    def execute_batch_upsert(self, table: str, columns: List[str], rows: List[tuple], unique_key: str = "job_id", update_columns: List[str] = None, retries: int = 2) -> int:
        if not rows:
            return 0
        
        last_error = None
        
        for attempt in range(retries + 1):
            conn = None
            try:
                conn = self._get_connection()
                column_names = ", ".join([f"`{col}`" for col in columns])
                placeholders = ", ".join(["%s"] * len(columns))
                
                update_cols = update_columns if update_columns is not None else [col for col in columns if col != unique_key]
                update_clause = ", ".join([f"`{col}` = VALUES(`{col}`)" for col in update_cols])
                sql = f"INSERT INTO `{table}` ({column_names}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"
                
                with conn.cursor() as cursor:
                    cursor.executemany(sql, rows)
                    conn.commit()
                    return cursor.rowcount
            except (pymysql.err.OperationalError, pymysql.err.DatabaseError, AttributeError) as e:
                last_error = e
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                
                if attempt < retries:
                    self._connection = None
                    backoff = 0.5 * (2 ** attempt)
                    logger.warning(f"Batch upsert error (attempt {attempt + 1}/{retries + 1}), retrying in {backoff:.1f}s")
                    time.sleep(backoff)
                else:
                    logger.error(f"Batch upsert failed after {retries + 1} attempts: {e}")
            except Exception as e:
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                logger.error(f"Batch upsert execution error: {e}")
                raise
        
        raise last_error if last_error else RuntimeError("Batch upsert failed")

    def create_tables(self) -> None:
        tables_sql = [
            """
            CREATE TABLE IF NOT EXISTS `review_orchestration_state` (
                id INT AUTO_INCREMENT PRIMARY KEY,
                job_id VARCHAR(255) NOT NULL UNIQUE,
                review_text LONGTEXT,
                rating INT,
                reviewer VARCHAR(255),
                location_name VARCHAR(255),
                review_date VARCHAR(50),
                sentiment VARCHAR(50),
                issue_type VARCHAR(50),
                key_issues JSON,
                tone VARCHAR(50),
                draft_response LONGTEXT,
                final_response LONGTEXT,
                response_type VARCHAR(50),
                compliance_status VARCHAR(50),
                compliance_reason LONGTEXT,
                needs_manual BOOLEAN,
                block_public_reply BOOLEAN,
                tone_score INT,
                brand_voice_score INT,
                completeness_score INT,
                overall_score INT,
                error LONGTEXT,
                logs JSON,
                history JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_job_id (job_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        ]

        tables_initialized = 0
        for sql in tables_sql:
            try:
                self.execute_update(sql)
                tables_initialized += 1
                logger.debug("Table created or already exists")
            except Exception as e:
                logger.error(f"Error creating table: {e}")
                raise
        logger.info(f"✅ Database tables initialized: {tables_initialized} tables ready")

db = PlanetScaleDB()
