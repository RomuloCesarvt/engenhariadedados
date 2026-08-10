"""
Auditoria de Vendas — cruza a base de VENDAS contra a base de LEADS, por empreendimento.

Pergunta que este módulo responde:
    "No Residencial Sol tivemos 5 vendas, 3 delas online. Das 5, quantas realmente
     têm lead digital na base DESTE empreendimento?"

O relatório comercial informa a origem *declarada* de cada venda. Este auditor
ignora essa declaração na hora de contar e refaz a atribuição do zero, buscando
cada comprador na base unificada de leads (Meta, Google, RD, BeeViral, Planilhas
e CV CRM).

Nada é somado entre empreendimentos: cada produto recebe sua própria conferência
fechada — seus leads, suas vendas, suas divergências — porque misturar obras
esconde justamente o erro que se quer achar.

Hierarquia de chaves de match (da mais forte para a mais fraca):
    CPF/CNPJ  >  ID de integração (gclid/fbclid/bee_id/rd_id)  >  e-mail  >  telefone  >  nome
"""

from typing import List, Dict, Optional, Tuple, NamedTuple
from datetime import datetime, timedelta, timezone

from engine.config import (
    LeadRecord,
    CVLeadRecord,
    SaleRecord,
    SaleAuditRecord,
    SalesChannelAudit,
    SalesAuditReport,
    EmpreendimentoAudit,
    SaleVerdict,
    MatchKey,
    OriginChannel,
    HealthStatus,
)
from engine.normalizer import (
    normalize_channel_alias,
    normalize_name,
    normalize_empreendimento,
    resolve_empreendimento,
    match_empreendimento,
    is_generic_empreendimento,
    clean_document,
    is_online_channel,
    EMPREENDIMENTO_DESCONHECIDO,
)

# Janela padrão de atribuição: um lead gerado até N dias antes da venda pode
# ser considerado a origem dela. No mercado imobiliário o ciclo é longo.
DEFAULT_ATTRIBUTION_WINDOW_DAYS = 180

# Tolerância para lead cadastrado logo após a venda (registro retroativo do corretor).
POST_SALE_GRACE = timedelta(hours=24)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class LeadRef(NamedTuple):
    """Referência enxuta a um lead indexado, vindo da origem ou do CV."""

    lead_id: str
    channel: OriginChannel
    created_at: datetime
    source: str  # "origem" (plataforma de mídia) ou "cv" (CRM)
    campaign: Optional[str] = None
    empreendimento: Optional[str] = None


class SalesAuditor:
    def __init__(
        self,
        sales: List[SaleRecord],
        source_leads: List[LeadRecord],
        cv_leads: List[CVLeadRecord],
        attribution_window_days: int = DEFAULT_ATTRIBUTION_WINDOW_DAYS,
        allow_name_match: bool = True,
        empreendimento: Optional[str] = None,
        catalogo_oficial: Optional[List[str]] = None,
        sales_available: bool = True,
    ):
        """
        `empreendimento` restringe a conferência às vendas daquele produto. Os leads
        dos demais empreendimentos continuam disponíveis para match — um comprador
        que entrou por outra campanha precisa ser reconhecido como tal, não virar
        "venda sem lead".
        """
        self.attribution_window = timedelta(days=attribution_window_days)
        self.attribution_window_days = attribution_window_days
        self.allow_name_match = allow_name_match
        self.empreendimento_filtro = empreendimento
        # Sem base de vendas, "lead sem venda" é falha de leitura, não inconsistência
        self.sales_available = sales_available

        self.source_leads = source_leads
        self.cv_leads = cv_leads

        # Catálogo oficial do CV ("Cidade - Nome - Código"). Quando existe, todo nome
        # de empreendimento vindo de planilha, campanha ou formulário é convertido
        # para o nome oficial — senão "Jardim dos Ipês" e "Taguaí - Jardim dos Ipês
        # - 12400" virariam dois produtos diferentes.
        self.catalogo_oficial = [c for c in (catalogo_oficial or []) if c]
        self.all_sales = [
            s.model_copy(update={"empreendimento": self._canonico(s.empreendimento)}) for s in sales
        ]

        # O catálogo completo (oficial + nomes que só existem nas bases) é o que
        # permite reconhecer o produto citado no nome da campanha de um lead.
        self.catalogo = self._build_catalogo()

        self.sales = self._apply_filtro(self.all_sales)

        # Cada índice guarda TODOS os leads de uma chave — o desempate é feito
        # depois, com a data e o empreendimento da venda em mãos.
        self.by_document: Dict[str, List[LeadRef]] = {}
        self.by_integration_id: Dict[str, List[LeadRef]] = {}
        self.by_email: Dict[str, List[LeadRef]] = {}
        self.by_phone: Dict[str, List[LeadRef]] = {}
        self.by_name: Dict[str, List[LeadRef]] = {}

        # Contagem de leads por empreendimento, alimentada durante a indexação
        self.leads_por_empreendimento: Dict[str, Dict[str, int]] = {}
        self.cv_leads_por_empreendimento: Dict[str, int] = {}
        self.leads_sem_empreendimento = 0

        self._build_indices()

    # ------------------------------------------------------------------
    # Catálogo e filtro
    # ------------------------------------------------------------------
    def _build_catalogo(self) -> List[str]:
        """Nomes oficiais de empreendimento, colhidos das vendas, do CV e dos leads."""
        vistos: Dict[str, str] = {}

        def registrar(nome: Optional[str]):
            if not nome or not str(nome).strip() or is_generic_empreendimento(nome):
                return
            chave = normalize_empreendimento(nome)
            if chave and chave not in vistos:
                vistos[chave] = str(nome).strip()

        for nome in self.catalogo_oficial:
            registrar(nome)
        for sale in self.all_sales:
            registrar(sale.empreendimento)
        for cv in self.cv_leads:
            registrar(self._canonico(cv.empreendimento))
        for lead in self.source_leads:
            registrar(self._canonico(lead.empreendimento))

        return list(vistos.values())

    def _canonico(self, nome: Optional[str]) -> Optional[str]:
        """Nome oficial do CV para um nome livre de empreendimento, quando identificável."""
        if not nome or not self.catalogo_oficial:
            return nome
        return match_empreendimento(nome, self.catalogo_oficial) or nome

    def _apply_filtro(self, sales: List[SaleRecord]) -> List[SaleRecord]:
        if not self.empreendimento_filtro:
            return sales
        alvo = normalize_empreendimento(self._canonico(self.empreendimento_filtro))
        return [s for s in sales if normalize_empreendimento(s.empreendimento) == alvo]

    def _lead_empreendimento(self, lead) -> Optional[str]:
        """
        Empreendimento de um lead: o campo explícito quando a fonte traz, senão o
        nome do produto citado na campanha.
        """
        explicito = getattr(lead, "empreendimento", None)
        if explicito and not is_generic_empreendimento(explicito):
            return self._canonico(explicito)
        return resolve_empreendimento(
            lead.raw_payload or {},
            getattr(lead, "campaign_name", None) or getattr(lead, "midia_cv", None),
            self.catalogo,
        )

    # ------------------------------------------------------------------
    # Indexação da base de leads
    # ------------------------------------------------------------------
    def _add(self, index: Dict[str, List[LeadRef]], key: Optional[str], ref: LeadRef):
        if key:
            index.setdefault(key, []).append(ref)

    def _build_indices(self):
        # 1. Leads das plataformas de origem — fonte de verdade do canal real
        for lead in self.source_leads:
            emp = self._lead_empreendimento(lead)
            ref = LeadRef(
                lead_id=lead.source_lead_id,
                channel=lead.origin_channel,
                created_at=ensure_utc(lead.created_at),
                source="origem",
                campaign=lead.campaign_name,
                empreendimento=emp,
            )
            if emp:
                bucket = self.leads_por_empreendimento.setdefault(emp, {})
                bucket[lead.origin_channel.value] = bucket.get(lead.origin_channel.value, 0) + 1
            else:
                self.leads_sem_empreendimento += 1

            payload = lead.raw_payload or {}
            self._add(self.by_document, clean_document(payload.get("cpf") or payload.get("documento")), ref)
            self._add(self.by_integration_id, lead.integration_id, ref)
            self._add(self.by_email, lead.email_clean, ref)
            self._add(self.by_phone, lead.phone_clean, ref)
            if self.allow_name_match:
                self._add(self.by_name, normalize_name(payload.get("nome") or payload.get("name")), ref)

        # 2. Leads do CV CRM — cobrem compradores que não aparecem nas plataformas
        for cv in self.cv_leads:
            emp = self._lead_empreendimento(cv)
            ref = LeadRef(
                lead_id=cv.cv_id,
                channel=normalize_channel_alias(cv.origem_cv),
                created_at=ensure_utc(cv.created_at),
                source="cv",
                campaign=cv.midia_cv,
                empreendimento=emp,
            )
            if emp:
                self.cv_leads_por_empreendimento[emp] = self.cv_leads_por_empreendimento.get(emp, 0) + 1

            payload = cv.raw_payload or {}
            self._add(self.by_document, clean_document(payload.get("cpf") or payload.get("documento")), ref)
            self._add(self.by_integration_id, cv.id_externo, ref)
            self._add(self.by_email, cv.email_clean, ref)
            self._add(self.by_phone, cv.phone_clean, ref)
            if self.allow_name_match:
                self._add(self.by_name, normalize_name(payload.get("nome") or payload.get("nome_cliente")), ref)

    # ------------------------------------------------------------------
    # Match de uma venda contra a base de leads
    # ------------------------------------------------------------------
    def _collect_candidates(self, sale: SaleRecord) -> List[Tuple[MatchKey, LeadRef]]:
        """Reúne todos os leads que batem com o comprador, por qualquer chave."""
        candidates: List[Tuple[MatchKey, LeadRef]] = []
        lookups = [
            (MatchKey.DOCUMENT, self.by_document, sale.document_clean),
            (MatchKey.INTEGRATION_ID, self.by_integration_id, sale.integration_id),
            (MatchKey.EMAIL, self.by_email, sale.email_clean),
            (MatchKey.PHONE, self.by_phone, sale.phone_clean),
        ]
        if self.allow_name_match:
            lookups.append((MatchKey.NAME, self.by_name, normalize_name(sale.client_name)))

        for key, index, value in lookups:
            if value:
                for ref in index.get(value, []):
                    candidates.append((key, ref))
        return candidates

    def _select_best(
        self, sale: SaleRecord, candidates: List[Tuple[MatchKey, LeadRef]]
    ) -> Tuple[Optional[Tuple[MatchKey, LeadRef]], bool]:
        """
        Escolhe o lead que melhor explica a venda.

        Retorna (melhor_candidato, houve_candidato_posterior_a_venda).
        Critérios, em ordem: dentro da janela de atribuição > mesmo empreendimento >
        canal online > força da chave > lead da plataforma de origem > mais recente.
        """
        sale_dt = ensure_utc(sale.sale_date)
        limit_before = sale_dt - self.attribution_window
        limit_after = sale_dt + POST_SALE_GRACE
        sale_emp = normalize_empreendimento(sale.empreendimento)

        valid: List[Tuple[MatchKey, LeadRef]] = []
        has_post_sale = False

        for key, ref in candidates:
            if ref.created_at > limit_after:
                has_post_sale = True
            elif ref.created_at >= limit_before:
                valid.append((key, ref))

        if not valid:
            return None, has_post_sale

        key_strength = {
            MatchKey.DOCUMENT: 4,
            MatchKey.INTEGRATION_ID: 3,
            MatchKey.EMAIL: 2,
            MatchKey.PHONE: 1,
            MatchKey.NAME: 0,
        }

        def score(item: Tuple[MatchKey, LeadRef]):
            key, ref = item
            mesmo_emp = (
                1 if sale_emp and normalize_empreendimento(ref.empreendimento) == sale_emp else 0
            )
            return (
                mesmo_emp,
                1 if is_online_channel(ref.channel) else 0,
                key_strength.get(key, 0),
                1 if ref.source == "origem" else 0,
                ref.created_at.timestamp(),
            )

        return max(valid, key=score), has_post_sale

    # ------------------------------------------------------------------
    # Auditoria
    # ------------------------------------------------------------------
    def audit(self, start_date: str, end_date: str) -> SalesAuditReport:
        audited: List[SaleAuditRecord] = []

        # Detecta o mesmo comprador em mais de uma venda no período
        buyer_keys: Dict[str, int] = {}
        for sale in self.sales:
            bkey = sale.document_clean or sale.email_clean or sale.phone_clean or normalize_name(sale.client_name)
            if bkey:
                buyer_keys[bkey] = buyer_keys.get(bkey, 0) + 1

        counters = {v: 0 for v in SaleVerdict}
        match_counters = {k: 0 for k in MatchKey}
        declared_by_channel: Dict[OriginChannel, int] = {}
        verified_by_channel: Dict[OriginChannel, int] = {}
        duplicate_buyers = 0
        vendas_sem_empreendimento = 0

        for sale in self.sales:
            candidates = self._collect_candidates(sale)
            best, has_post_sale = self._select_best(sale, candidates)

            matched_key = MatchKey.NONE
            matched_ref: Optional[LeadRef] = None
            if best:
                matched_key, matched_ref = best

            verified_is_online = bool(matched_ref and is_online_channel(matched_ref.channel))
            days_gap = None
            if matched_ref:
                days_gap = (ensure_utc(sale.sale_date) - matched_ref.created_at).days

            if not sale.empreendimento:
                vendas_sem_empreendimento += 1

            # Lead do mesmo produto ou de outro?
            sale_emp_key = normalize_empreendimento(sale.empreendimento)
            lead_emp_key = normalize_empreendimento(matched_ref.empreendimento) if matched_ref else None
            empreendimento_match: Optional[bool] = None
            if matched_ref and sale_emp_key and lead_emp_key:
                empreendimento_match = sale_emp_key == lead_emp_key

            # ---------------- Veredito ----------------
            if sale.declared_is_online and not matched_ref and has_post_sale:
                verdict = SaleVerdict.LEAD_AFTER_SALE
                severity = "HIGH"
                details = (
                    "Venda declarada como online, mas o único lead encontrado para este comprador "
                    "foi criado DEPOIS da venda — cadastro retroativo, não comprova origem digital."
                )
            elif sale.declared_is_online and not verified_is_online:
                verdict = SaleVerdict.ONLINE_UNPROVEN
                severity = "HIGH"
                if matched_ref:
                    details = (
                        f"Venda declarada como online ('{sale.declared_channel_raw}'), porém o comprador "
                        f"só aparece na base como {self._channel_label(matched_ref.channel)} "
                        f"({matched_ref.source}) — não há lead de mídia digital."
                    )
                else:
                    details = (
                        f"Venda declarada como online ('{sale.declared_channel_raw}'), mas o comprador "
                        "NÃO foi encontrado em nenhuma base de leads (CPF, e-mail, telefone ou ID de integração). "
                        "Online do relatório está inflado nesta venda."
                    )
            elif sale.declared_is_online and verified_is_online:
                declared_ch = sale.declared_channel
                if declared_ch and matched_ref and declared_ch != matched_ref.channel:
                    verdict = SaleVerdict.CHANNEL_MISMATCH
                    severity = "MEDIUM"
                    details = (
                        f"Venda online confirmada, porém atribuída ao canal errado: relatório diz "
                        f"'{sale.declared_channel_raw}' e o lead veio de {self._channel_label(matched_ref.channel)}."
                    )
                else:
                    verdict = SaleVerdict.ONLINE_CONFIRMED
                    severity = "NONE"
                    details = (
                        f"Online confirmado: lead {matched_ref.lead_id} em "
                        f"{self._channel_label(matched_ref.channel)}, match por {matched_key.value}, "
                        f"{days_gap} dia(s) antes da venda."
                    )
            elif not sale.declared_is_online and verified_is_online:
                verdict = SaleVerdict.ONLINE_NOT_DECLARED
                severity = "MEDIUM"
                details = (
                    f"Venda declarada como '{sale.declared_channel_raw}' (offline), mas o comprador tem lead "
                    f"em {self._channel_label(matched_ref.channel)} criado {days_gap} dia(s) antes da venda "
                    f"(match por {matched_key.value}). Online do relatório está subnotificado."
                )
            else:
                verdict = SaleVerdict.OFFLINE_CONFIRMED
                severity = "NONE"
                if matched_ref:
                    details = (
                        f"Offline coerente: comprador consta como {self._channel_label(matched_ref.channel)} "
                        f"(match por {matched_key.value})."
                    )
                else:
                    details = (
                        "Offline coerente: comprador não consta em nenhuma base de leads digital "
                        "— venda de origem presencial/espontânea."
                    )

            # ---------------- Ressalvas ----------------
            if empreendimento_match is False:
                details += (
                    f" ⚠ O lead deste comprador é do empreendimento '{matched_ref.empreendimento}', "
                    f"não de '{sale.empreendimento}' — cliente migrou de produto."
                )

            bkey = sale.document_clean or sale.email_clean or sale.phone_clean or normalize_name(sale.client_name)
            if bkey and buyer_keys.get(bkey, 0) > 1:
                duplicate_buyers += 1
                details += f" ⚠ Comprador aparece em {buyer_keys[bkey]} vendas no período — verifique dupla contagem."

            if matched_key == MatchKey.NAME:
                details += " ⚠ Match obtido apenas por nome (confiança baixa) — confirme com CPF."

            if matched_ref and has_post_sale:
                details += " ⚠ Existe também lead criado após a venda para este comprador."

            counters[verdict] += 1
            match_counters[matched_key] += 1

            if sale.declared_channel:
                declared_by_channel[sale.declared_channel] = declared_by_channel.get(sale.declared_channel, 0) + 1
            if matched_ref:
                verified_by_channel[matched_ref.channel] = verified_by_channel.get(matched_ref.channel, 0) + 1

            audited.append(
                SaleAuditRecord(
                    sale_id=sale.sale_id,
                    client_name=sale.client_name,
                    document=sale.document,
                    email=sale.email_clean or sale.email,
                    phone=sale.phone_clean or sale.phone,
                    sale_date=sale.sale_date.isoformat(),
                    value=sale.value,
                    empreendimento=sale.empreendimento,
                    declared_channel_raw=sale.declared_channel_raw,
                    declared_is_online=sale.declared_is_online,
                    verified_is_online=verified_is_online,
                    verdict=verdict,
                    severity=severity,
                    matched_by=matched_key,
                    matched_lead_id=matched_ref.lead_id if matched_ref else None,
                    matched_channel=matched_ref.channel if matched_ref else None,
                    lead_created_at=matched_ref.created_at.isoformat() if matched_ref else None,
                    days_lead_to_sale=days_gap,
                    lead_empreendimento=matched_ref.empreendimento if matched_ref else None,
                    empreendimento_match=empreendimento_match,
                    details=details,
                )
            )

        # ---------------- Consolidação ----------------
        total = len(self.sales)
        declared_online = sum(1 for s in audited if s.declared_is_online)
        verified_online = sum(1 for s in audited if s.verified_is_online)

        # Acurácia: vendas cuja origem declarada bate integralmente com a comprovada.
        # CHANNEL_MISMATCH conta como erro — o online está certo, mas o canal não.
        correct = counters[SaleVerdict.ONLINE_CONFIRMED] + counters[SaleVerdict.OFFLINE_CONFIRMED]
        accuracy = round(correct / total * 100, 1) if total else 100.0
        health = self._health_from_accuracy(accuracy)

        channels: List[SalesChannelAudit] = []
        for ch in OriginChannel:
            if ch == OriginChannel.CV_CRM:
                continue
            dec = declared_by_channel.get(ch, 0)
            ver = verified_by_channel.get(ch, 0)
            if dec or ver:
                channels.append(
                    SalesChannelAudit(channel=ch, declared_sales=dec, verified_sales=ver, delta=ver - dec)
                )

        return SalesAuditReport(
            start_date=start_date,
            end_date=end_date,
            attribution_window_days=self.attribution_window_days,
            total_sales=total,
            declared_online=declared_online,
            declared_offline=total - declared_online,
            verified_online=verified_online,
            verified_offline=total - verified_online,
            online_confirmed=counters[SaleVerdict.ONLINE_CONFIRMED],
            online_unproven=counters[SaleVerdict.ONLINE_UNPROVEN],
            online_not_declared=counters[SaleVerdict.ONLINE_NOT_DECLARED],
            offline_confirmed=counters[SaleVerdict.OFFLINE_CONFIRMED],
            channel_mismatch=counters[SaleVerdict.CHANNEL_MISMATCH],
            lead_after_sale=counters[SaleVerdict.LEAD_AFTER_SALE],
            duplicate_buyers=duplicate_buyers,
            online_delta=verified_online - declared_online,
            attribution_accuracy=accuracy,
            health_status=health,
            matched_by_document=match_counters[MatchKey.DOCUMENT],
            matched_by_integration_id=match_counters[MatchKey.INTEGRATION_ID],
            matched_by_email=match_counters[MatchKey.EMAIL],
            matched_by_phone=match_counters[MatchKey.PHONE],
            matched_by_name=match_counters[MatchKey.NAME],
            unmatched=match_counters[MatchKey.NONE],
            low_confidence_matches=match_counters[MatchKey.NAME],
            empreendimentos=self._build_empreendimentos(audited),
            leads_sem_empreendimento=self.leads_sem_empreendimento,
            vendas_sem_empreendimento=vendas_sem_empreendimento,
            empreendimento_filtro=self.empreendimento_filtro,
            sales_base_available=self.sales_available,
            channels=channels,
            sales=audited,
        )

    # ------------------------------------------------------------------
    # Conferência fechada por empreendimento
    # ------------------------------------------------------------------
    def _build_empreendimentos(self, audited: List[SaleAuditRecord]) -> List[EmpreendimentoAudit]:
        """Uma conferência independente por produto — nada é somado entre obras."""
        # Agrupa as vendas auditadas
        grupos: Dict[str, List[SaleAuditRecord]] = {}
        rotulos: Dict[str, str] = {}
        for sale in audited:
            nome = sale.empreendimento or EMPREENDIMENTO_DESCONHECIDO
            chave = normalize_empreendimento(nome) or nome
            grupos.setdefault(chave, []).append(sale)
            rotulos.setdefault(chave, nome)

        # Empreendimentos que só têm leads (nenhuma venda) também precisam aparecer:
        # zero venda com muito lead é exatamente o tipo de buraco a investigar.
        if not self.empreendimento_filtro:
            for nome in self.leads_por_empreendimento:
                chave = normalize_empreendimento(nome) or nome
                grupos.setdefault(chave, [])
                rotulos.setdefault(chave, nome)

        resultado: List[EmpreendimentoAudit] = []
        for chave, vendas in grupos.items():
            nome = rotulos[chave]
            leads_by_channel = self._leads_do_empreendimento(chave)
            total_leads = sum(leads_by_channel.values())
            total_cv = self._cv_leads_do_empreendimento(chave)

            total_sales = len(vendas)
            declared_online = sum(1 for v in vendas if v.declared_is_online)
            verified_online = sum(1 for v in vendas if v.verified_is_online)
            online_confirmed = sum(1 for v in vendas if v.verdict == SaleVerdict.ONLINE_CONFIRMED)
            online_unproven = sum(1 for v in vendas if v.verdict == SaleVerdict.ONLINE_UNPROVEN)
            online_not_declared = sum(1 for v in vendas if v.verdict == SaleVerdict.ONLINE_NOT_DECLARED)
            offline_confirmed = sum(1 for v in vendas if v.verdict == SaleVerdict.OFFLINE_CONFIRMED)
            channel_mismatch = sum(1 for v in vendas if v.verdict == SaleVerdict.CHANNEL_MISMATCH)
            lead_after_sale = sum(1 for v in vendas if v.verdict == SaleVerdict.LEAD_AFTER_SALE)
            cross = sum(1 for v in vendas if v.empreendimento_match is False)
            sem_lead = sum(1 for v in vendas if v.matched_by == MatchKey.NONE)
            total_value = sum(v.value or 0.0 for v in vendas)

            correct = online_confirmed + offline_confirmed
            accuracy = round(correct / total_sales * 100, 1) if total_sales else 100.0
            conversion = round(total_sales / total_leads * 100, 1) if total_leads else 0.0

            inconsistencias = self._diagnosticar(
                nome=nome,
                total_leads=total_leads,
                total_sales=total_sales,
                online_unproven=online_unproven,
                online_not_declared=online_not_declared,
                channel_mismatch=channel_mismatch,
                lead_after_sale=lead_after_sale,
                cross=cross,
                sem_lead=sem_lead,
                verified_online=verified_online,
                sales_available=self.sales_available,
            )

            resultado.append(
                EmpreendimentoAudit(
                    empreendimento=nome,
                    total_leads=total_leads,
                    leads_by_channel=leads_by_channel,
                    total_cv_leads=total_cv,
                    total_sales=total_sales,
                    total_value=round(total_value, 2),
                    declared_online=declared_online,
                    verified_online=verified_online,
                    online_delta=verified_online - declared_online,
                    online_confirmed=online_confirmed,
                    online_unproven=online_unproven,
                    online_not_declared=online_not_declared,
                    offline_confirmed=offline_confirmed,
                    channel_mismatch=channel_mismatch,
                    cross_empreendimento_sales=cross,
                    sales_without_lead=sem_lead,
                    conversion_rate=conversion,
                    attribution_accuracy=accuracy,
                    health_status=self._health_from_accuracy(accuracy),
                    is_consistent=not inconsistencias,
                    inconsistencies=inconsistencias,
                    sales=vendas,
                )
            )

        # Maior volume de vendas primeiro; "Não identificado" sempre por último
        resultado.sort(
            key=lambda e: (e.empreendimento == EMPREENDIMENTO_DESCONHECIDO, -e.total_sales, -e.total_leads)
        )
        return resultado

    def _leads_do_empreendimento(self, chave: str) -> Dict[str, int]:
        for nome, canais in self.leads_por_empreendimento.items():
            if (normalize_empreendimento(nome) or nome) == chave:
                return dict(canais)
        return {}

    def _cv_leads_do_empreendimento(self, chave: str) -> int:
        for nome, qtd in self.cv_leads_por_empreendimento.items():
            if (normalize_empreendimento(nome) or nome) == chave:
                return qtd
        return 0

    @staticmethod
    def _diagnosticar(
        nome: str,
        total_leads: int,
        total_sales: int,
        online_unproven: int,
        online_not_declared: int,
        channel_mismatch: int,
        lead_after_sale: int,
        cross: int,
        sem_lead: int,
        verified_online: int,
        sales_available: bool = True,
    ) -> List[str]:
        """Traduz os números do empreendimento em problemas acionáveis."""
        problemas: List[str] = []

        if nome == EMPREENDIMENTO_DESCONHECIDO:
            problemas.append(
                f"{total_sales} venda(s) sem empreendimento informado na base de origem — "
                "impossível conferir por produto até a coluna ser preenchida."
            )

        if online_unproven:
            problemas.append(
                f"{online_unproven} venda(s) declarada(s) como online sem nenhum lead digital na base — "
                "o online deste empreendimento está inflado."
            )
        if lead_after_sale:
            problemas.append(
                f"{lead_after_sale} venda(s) online cujo lead foi cadastrado depois da venda — "
                "cadastro retroativo não comprova origem."
            )
        if online_not_declared:
            problemas.append(
                f"{online_not_declared} venda(s) marcada(s) como offline vieram de mídia digital — "
                "o online deste empreendimento está subnotificado."
            )
        if channel_mismatch:
            problemas.append(
                f"{channel_mismatch} venda(s) online creditada(s) ao canal errado."
            )
        if cross:
            problemas.append(
                f"{cross} venda(s) cujo comprador entrou por campanha de OUTRO empreendimento — "
                "confira se a verba está sendo creditada ao produto certo."
            )
        if total_sales and total_leads == 0:
            problemas.append(
                "Há vendas registradas, mas nenhum lead atribuído a este empreendimento — "
                "campanhas sem identificação do produto ou base de leads não integrada."
            )
        if total_leads and not total_sales and sales_available:
            problemas.append(
                f"{total_leads} lead(s) captado(s) e nenhuma venda no período — "
                "verifique se as vendas deste empreendimento entraram na base."
            )
        if verified_online > total_leads and total_leads:
            problemas.append(
                f"{verified_online} venda(s) online para apenas {total_leads} lead(s) — "
                "número impossível, revise a identificação do empreendimento nas campanhas."
            )
        # Venda presencial sem lead digital é o esperado, não inconsistência; a venda
        # online sem lead já foi apontada acima como online inflado.
        return problemas

    @staticmethod
    def _health_from_accuracy(accuracy: float) -> HealthStatus:
        if accuracy >= 98.0:
            return HealthStatus.HEALTHY
        if accuracy >= 93.0:
            return HealthStatus.WARNING
        return HealthStatus.CRITICAL

    @staticmethod
    def _channel_label(channel: Optional[OriginChannel]) -> str:
        labels = {
            OriginChannel.META_ADS: "Meta Ads",
            OriginChannel.GOOGLE_ADS: "Google Ads",
            OriginChannel.RD_STATION: "RD Station",
            OriginChannel.BEEVIRAL: "BeeViral",
            OriginChannel.SHEETS_BI: "Planilhas/Eventos (offline)",
            OriginChannel.CV_CRM: "CV CRM",
        }
        return labels.get(channel, "desconhecido") if channel else "desconhecido"

    # ------------------------------------------------------------------
    def listar_empreendimentos(self) -> List[str]:
        """Empreendimentos disponíveis para filtro, na ordem do catálogo."""
        return list(self.catalogo)
