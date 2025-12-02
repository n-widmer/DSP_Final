-- dsp_final_schema.sql
-- Schema-only SQL for DSP_Final (creates database and patients table)

CREATE DATABASE IF NOT EXISTS `dsp_final` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `dsp_final`;

CREATE TABLE IF NOT EXISTS `patients` (
  `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `first_name` VARCHAR(100),
  `last_name` VARCHAR(100),
  `gender` TINYINT(1) DEFAULT NULL,
  `age` INT DEFAULT NULL,
  `weight` FLOAT DEFAULT NULL,
  `height` FLOAT DEFAULT NULL,
  `health_history` TEXT,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
