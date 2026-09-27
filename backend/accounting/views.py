from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import date

from .models import Account, Party, Voucher
from .serializers import AccountSerializer, PartySerializer, VoucherSerializer
from .services import party_ledger, account_ledger, trial_balance, profit_and_loss, pnl_detailed, cash_book, balance_sheet


def _filter_business(qs, request):
    biz = request.query_params.get('business')
    return qs.filter(business=biz) if biz else qs


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        atype = self.request.query_params.get('type')
        if atype:
            qs = qs.filter(type=atype)
        return _filter_business(qs, self.request)


class PartyViewSet(viewsets.ModelViewSet):
    queryset = Party.objects.select_related('control_account').all()
    serializer_class = PartySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        ptype = self.request.query_params.get('party_type')
        if ptype:
            qs = qs.filter(party_type__in=[ptype, 'BOTH'])
        return _filter_business(qs, self.request)


class VoucherViewSet(viewsets.ReadOnlyModelViewSet):
    """Vouchers are created via business-module actions (post_voucher), not
    edited directly — so this is read-only. Corrections use reverse."""
    queryset = Voucher.objects.prefetch_related('entries').all()
    serializer_class = VoucherSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        vtype = self.request.query_params.get('type')
        if vtype:
            qs = qs.filter(type=vtype)
        return _filter_business(qs, self.request)


# ─── Reports (read-only, derived) ───

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def party_statement(request, party_id):
    party = Party.objects.get(id=party_id)
    df = request.query_params.get('from')
    dt = request.query_params.get('to')
    return Response(party_ledger(party, date_from=df, date_to=dt))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def account_statement(request, account_id):
    account = Account.objects.get(id=account_id)
    df = request.query_params.get('from')
    dt = request.query_params.get('to')
    biz = request.query_params.get('business')
    return Response(account_ledger(account, date_from=df, date_to=dt, business=biz))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trial_balance_view(request):
    upto = request.query_params.get('upto')
    biz = request.query_params.get('business')
    return Response(trial_balance(upto=upto, business=biz))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profit_and_loss_view(request):
    df = request.query_params.get('from') or date.today().replace(day=1).isoformat()
    dt = request.query_params.get('to') or date.today().isoformat()
    biz = request.query_params.get('business')
    detailed = request.query_params.get('detailed') == '1'
    if detailed:
        return Response(pnl_detailed(df, dt, business=biz))
    return Response(profit_and_loss(df, dt, business=biz))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cash_book_view(request):
    df = request.query_params.get('from') or date.today().replace(day=1).isoformat()
    dt = request.query_params.get('to') or date.today().isoformat()
    biz = request.query_params.get('business')
    return Response(cash_book(df, dt, business=biz))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def outstanding_view(request):
    """Who owes what (and what we owe). Positive = receivable, negative = payable."""
    biz = request.query_params.get('business')
    qs = Party.objects.all()
    if biz:
        qs = qs.filter(business=biz)
    rows = []
    for p in qs:
        bal = p.balance()
        if bal == 0:
            continue
        rows.append({'party_id': p.id, 'name': p.name, 'phone': p.phone,
                     'party_type': p.party_type, 'balance': bal})
    receivable = sum(r['balance'] for r in rows if r['balance'] > 0)
    payable = -sum(r['balance'] for r in rows if r['balance'] < 0)
    rows.sort(key=lambda r: r['balance'], reverse=True)
    return Response({'rows': rows, 'total_receivable': receivable,
                     'total_payable': payable})


# ─── BOOK LOCK (day-close) ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def book_lock(request):
    """GET: current lock date for a business (?business=). POST (admin only):
    set closed_through to lock, or null/empty to re-open. Logged."""
    from .models import BookLock, AuditLog
    biz = request.query_params.get('business') or request.data.get('business') or 'chicken_center'

    if request.method == 'GET':
        return Response({'business': biz, 'closed_through': BookLock.closed_date_for(biz)})

    # POST — admin only
    profile = getattr(request.user, 'profile', None)
    if not profile or not profile.is_admin:
        return Response({'error': 'Only an admin can close or re-open the books.'}, status=403)

    closed_through = request.data.get('closed_through') or None
    row, _ = BookLock.objects.get_or_create(business=biz)
    prev = row.closed_through
    row.closed_through = closed_through
    row.updated_by = request.user
    row.save()
    AuditLog.objects.create(
        user=request.user, action='EDIT', object_type='BookLock', object_id=biz,
        detail={'from': str(prev), 'to': str(closed_through)},
    )
    return Response({'business': biz, 'closed_through': row.closed_through})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def balance_sheet_view(request):
    upto = request.query_params.get('upto')
    biz = request.query_params.get('business')
    return Response(balance_sheet(upto=upto, business=biz))
