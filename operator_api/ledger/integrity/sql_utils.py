def drop_ledger_constraint_if_exists(table_name, constraint_name):
    return "ALTER TABLE ledger_{} DROP CONSTRAINT IF EXISTS {};".format(table_name, constraint_name)


def drop_ledger_trigger_if_exists(table_name, trigger_name):
    return "DROP TRIGGER IF EXISTS {} ON ledger_{} CASCADE;".format(trigger_name, table_name)
