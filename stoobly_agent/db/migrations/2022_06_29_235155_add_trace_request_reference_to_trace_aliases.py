from orator.migrations import Migration


class AddTraceRequestReferenceToTraceAliases(Migration):

    def up(self):
        """
        Run the migrations.
        """
        with self.schema.table('trace_aliases') as table:
            table.string('trace_request_id').unsigned().nullable()
            table.string('trace_request_id').references('id').on('trace_requests').index() 

    def down(self):
        """
        Revert the migrations.
        """
        with self.schema.table('trace_aliases') as table:
            table.drop_column('trace_request_id')
