from operator_api.locked_admin import ReadOnlyModelAdmin


class ContractStateAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'block',
        'confirmed',
        'last_checkpoint_submission_eon',
        'last_checkpoint',
        'basis',
        'is_checkpoint_submitted_for_current_eon',
        'has_missed_checkpoint_submission',
        'live_challenge_count',
    ]

    list_display = [
        'block',
        'eon_number',
        'sub_block',
        'confirmed',
        'last_submission',
        'submitted',
        'missed',
        'live_challenges',
    ]

    def last_submission(self, obj):
        return obj.last_checkpoint_submission_eon

    def submitted(self, obj):
        return obj.is_checkpoint_submitted_for_current_eon
    submitted.boolean = True

    def missed(self, obj):
        return obj.has_missed_checkpoint_submission
    missed.boolean = True

    def live_challenges(self, obj):
        return obj.live_challenge_count
