/* produce SQL migration code to ensure utf8mb4 character set and collation for tables and columns */
/* kindly inspired by zabbix migration scripts */
SELECT   CONCAT('ALTER TABLE ', table_schema, '.`', table_name, '`',
		                   ' MODIFY COLUMN `', column_name, '` ', column_type,
		                   ' CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci',
		                case
		                    when column_default is null then ''
		                    else concat(' default ', column_default, ' ')
		                end,
		                case
		                    when is_nullable = 'no' then ' not null '
		                    else ''
		                end,
		            ';') AS command
FROM information_schema.columns
WHERE table_schema = 'pydici'
     AND (column_type like 'varchar%'
            OR column_type like 'char%'
            OR column_type = 'longtext')

union

SELECT CONCAT('ALTER TABLE ', table_schema, '.`', table_name, '`',
		                   ' CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;') AS command
		        FROM information_schema.tables
		        WHERE table_schema = 'pydici'
