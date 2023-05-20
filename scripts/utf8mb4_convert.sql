/* adapted from zabbix convert procedure
*/

DELIMITER $$
DROP PROCEDURE IF EXISTS convert_utf8;
CREATE PROCEDURE convert_utf8 (
)

BEGIN
	declare cmd varchar(255) default "";
	declare finished integer default 0;

	declare cur_command cursor for 
		SELECT command
		FROM
		    (/* This 'select' statement deals with 'text' type columns to prevent
		        their automatic conversion into 'mediumtext' type.
		     */
		     SELECT table_name AS sort1,
		                   'A' AS sort2,
		            CONCAT('ALTER TABLE ', table_schema, '.', table_name,
		                   ' MODIFY COLUMN ', column_name, ' ', column_type,
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
		           AND column_type = 'text'
		    UNION
		     /* This 'select' statement deals with setting character set and collation for
		        each table and converting varchar fields on a per-table basis.
		     */
		     SELECT table_name AS sort1,
		                   'B' AS sort2,
		            CONCAT('ALTER TABLE ', table_schema, '.', table_name,
		                   ' CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;') AS command
		        FROM information_schema.tables
		        WHERE table_schema = 'pydici') s
		/* Sorting is important: 'MODIFY COLUMN' statements should precede 'CONVERT TO' ones
		   for each table. */
		ORDER BY sort1, sort2;
	
	declare continue handler for not found set finished = 1;

	open cur_command;
	cmd_loop: loop
		fetch cur_command into cmd;
		if finished = 1 then
			leave cmd_loop;
		end if;
		SET @value = cmd;
		PREPARE stmt FROM @value;
		EXECUTE stmt;
		DEALLOCATE PREPARE stmt;
	end loop cmd_loop;
	close cur_command;

END$$

DELIMITER ;
call convert_utf8();
drop PROCEDURE convert_utf8;
