"""Case picker and case-scoped registration page for GeoProfiler."""

from __future__ import annotations

from datetime import date

import streamlit as st

from src.crime_import import (
    CANONICAL_IMPORT_FIELDS,
    REQUIRED_IMPORT_FIELDS,
    apply_column_mapping,
    guess_column_mapping,
    read_uploaded_table,
)
from src.data_manager import (
    Caso,
    CasoInput,
    CrimeInput,
    create_caso,
    link_casos,
    list_casos,
    list_linked_casos,
    prepare_crime_data,
    save_case_crime_record,
    save_case_crime_records_bulk,
    set_caso_archived,
    unlink_casos,
    update_caso,
    validate_coordinates,
)
from src.geocoding import geocode_address
from src.pages._shared import (
    format_crime_table,
    get_caso,
    inject_global_styles,
    load_case_crimes,
    render_badge,
    render_case_header,
    render_header,
    render_metric_card,
    render_sidebar,
)
from src.utils import normalize_column_names


def main() -> None:
    """Render the case picker or the active case's workspace."""
    settings = render_sidebar()
    inject_global_styles(settings)
    render_header()

    st.markdown("### Casos")

    active_caso_id = st.session_state.get("active_caso_id")
    active_caso = get_caso(active_caso_id) if active_caso_id else None

    if active_caso is None:
        st.session_state.pop("active_caso_id", None)
        render_case_list()
        render_new_case_form()
    else:
        render_active_case(active_caso)


def render_case_list() -> None:
    """List existing cases with a button to open each one."""
    show_archived = st.checkbox("Mostrar casos arquivados", value=False, key="show_archived_casos")
    casos = list_casos(include_archived=show_archived)
    if casos.empty:
        st.info("Nenhum caso cadastrado ainda. Crie o primeiro caso abaixo.")
        return

    st.markdown("#### Casos existentes")
    for _, row in casos.iterrows():
        is_archived = bool(row["arquivado"])
        with st.container(border=True):
            cols = st.columns([3, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{row['nome']}**")
                if is_archived:
                    st.markdown(render_badge("Arquivado", "neutral"), unsafe_allow_html=True)
                if row["descricao"]:
                    st.caption(row["descricao"])
            with cols[1]:
                st.metric("Ocorrências", int(row["total_crimes"]))
            with cols[2]:
                st.caption("Aberto em")
                st.write(row["data_abertura"] or "-")
            with cols[3]:
                label = "Reativar" if is_archived else "Abrir"
                icon = ":material/unarchive:" if is_archived else ":material/open_in_new:"
                if st.button(label, key=f"abrir_caso_{row['id']}", icon=icon, width="stretch"):
                    if is_archived:
                        set_caso_archived(int(row["id"]), False)
                    st.session_state["active_caso_id"] = int(row["id"])
                    st.switch_page("src/pages/mapa.py")


def render_new_case_form() -> None:
    """Render the form used to create a new case."""
    st.markdown("#### Novo caso")
    with st.form("novo_caso_form", clear_on_submit=True):
        nome = st.text_input("Nome do caso", placeholder="Ex.: Série de roubos - Zona Sul")
        descricao = st.text_area("Descrição", height=80)
        form_cols = st.columns(2)
        with form_cols[0]:
            responsavel = st.text_input("Responsável", placeholder="Ex.: Investigador responsável")
        with form_cols[1]:
            data_abertura = st.date_input("Data de abertura", value=date.today())
        notas = st.text_area("Notas", height=80)
        barreiras_geograficas = st.text_area(
            "Barreiras geográficas (opcional)",
            height=80,
            placeholder="Ex.: Rio Pinheiros a oeste, Marginal Tietê ao norte",
            help="Rios, rodovias ou outras barreiras que possam limitar o deslocamento do infrator.",
        )
        submitted = st.form_submit_button("Criar caso", icon=":material/save:", width="stretch")

    if not submitted:
        return

    if not nome.strip():
        st.error("Informe o nome do caso.")
        return

    caso_id = create_caso(
        CasoInput(
            nome=nome,
            descricao=descricao,
            responsavel=responsavel,
            data_abertura=data_abertura,
            notas=notas,
            barreiras_geograficas=barreiras_geograficas,
        )
    )
    st.session_state["active_caso_id"] = caso_id
    st.rerun()


def render_active_case(caso: Caso) -> None:
    """Render the active case's header, registration form, and crime table."""
    render_case_header(caso)

    action_cols = st.columns([1, 1, 6])
    with action_cols[0]:
        if st.button("Trocar caso", icon=":material/swap_horiz:"):
            st.session_state.pop("active_caso_id", None)
            st.rerun()
    with action_cols[1]:
        toggle_label = "Reativar caso" if caso.arquivado else "Arquivar caso"
        toggle_icon = ":material/unarchive:" if caso.arquivado else ":material/archive:"
        if st.button(toggle_label, icon=toggle_icon):
            set_caso_archived(caso.id, not caso.arquivado)
            st.rerun()

    if caso.arquivado:
        st.info(
            "Este caso está arquivado. Ele continua totalmente utilizável enquanto "
            "estiver aberto, mas não aparece na lista padrão de casos."
        )

    render_edit_case_form(caso)
    render_related_cases_section(caso)
    render_registration_form(caso.id)
    render_import_section(caso.id)

    crimes = load_case_crimes(caso.id)

    metric_cols = st.columns(3)
    render_metric_card(metric_cols[0], "list_alt", "Ocorrências", str(len(crimes)), "Registros válidos")
    render_metric_card(
        metric_cols[1],
        "category",
        "Tipos de crime",
        str(crimes["tipo_crime"].nunique()) if not crimes.empty else "0",
        "Categorias distintas",
    )
    render_metric_card(metric_cols[2], "badge", "Responsável", caso.responsavel or "Não informado", "Caso")

    st.markdown("#### Ocorrências cadastradas")
    st.dataframe(format_crime_table(crimes), width="stretch", hide_index=True)


def render_edit_case_form(caso: Caso) -> None:
    """Render a collapsed form to edit the active case's metadata."""
    with st.expander("Editar caso"):
        try:
            data_abertura_value = date.fromisoformat(caso.data_abertura)
        except (TypeError, ValueError):
            data_abertura_value = date.today()

        with st.form("editar_caso_form"):
            nome = st.text_input("Nome do caso", value=caso.nome)
            descricao = st.text_area("Descrição", value=caso.descricao, height=80)
            form_cols = st.columns(2)
            with form_cols[0]:
                responsavel = st.text_input("Responsável", value=caso.responsavel)
            with form_cols[1]:
                data_abertura = st.date_input("Data de abertura", value=data_abertura_value)
            notas = st.text_area("Notas", value=caso.notas, height=80)
            barreiras_geograficas = st.text_area(
                "Barreiras geográficas (opcional)",
                value=caso.barreiras_geograficas,
                height=80,
                placeholder="Ex.: Rio Pinheiros a oeste, Marginal Tietê ao norte",
                help="Rios, rodovias ou outras barreiras que possam limitar o deslocamento do infrator.",
            )
            submitted = st.form_submit_button("Salvar alterações", icon=":material/save:", width="stretch")

        if not submitted:
            return

        if not nome.strip():
            st.error("Informe o nome do caso.")
            return

        update_caso(
            caso.id,
            CasoInput(
                nome=nome,
                descricao=descricao,
                responsavel=responsavel,
                data_abertura=data_abertura,
                notas=notas,
                barreiras_geograficas=barreiras_geograficas,
            ),
        )
        st.success("Caso atualizado com sucesso.")
        st.rerun()


def render_related_cases_section(caso: Caso) -> None:
    """Render linked cases with switch-to/unlink controls, plus a link-new control."""
    with st.expander("Casos relacionados"):
        linked = list_linked_casos(caso.id)
        if linked.empty:
            st.caption("Nenhum caso relacionado ainda.")
        else:
            for _, row in linked.iterrows():
                link_cols = st.columns([3, 1, 1])
                with link_cols[0]:
                    st.markdown(f"**{row['nome']}**")
                    if row["descricao"]:
                        st.caption(row["descricao"])
                with link_cols[1]:
                    if st.button(
                        "Abrir",
                        key=f"abrir_relacionado_{row['id']}",
                        icon=":material/open_in_new:",
                        width="stretch",
                    ):
                        st.session_state["active_caso_id"] = int(row["id"])
                        st.switch_page("src/pages/mapa.py")
                with link_cols[2]:
                    if st.button(
                        "Desvincular",
                        key=f"desvincular_{row['id']}",
                        icon=":material/link_off:",
                        width="stretch",
                    ):
                        unlink_casos(caso.id, int(row["id"]))
                        st.rerun()

        st.divider()
        candidates = list_casos()
        candidates = candidates[candidates["id"] != caso.id]
        linked_ids = set(linked["id"]) if not linked.empty else set()
        candidates = candidates[~candidates["id"].isin(linked_ids)]

        if candidates.empty:
            st.caption("Nenhum outro caso disponível para vincular.")
            return

        options = {int(row["id"]): row["nome"] for _, row in candidates.iterrows()}
        selected_id = st.selectbox(
            "Vincular a outro caso",
            options=list(options.keys()),
            format_func=lambda cid: options[cid],
            key=f"link_target_{caso.id}",
        )
        if st.button("Vincular", key=f"vincular_{caso.id}", icon=":material/link:"):
            link_casos(caso.id, selected_id)
            st.rerun()


DEFAULT_LATITUDE = -23.550520
DEFAULT_LONGITUDE = -46.633308
LATITUDE_KEY = "crime_latitude_input"
LONGITUDE_KEY = "crime_longitude_input"


def render_registration_form(caso_id: int) -> None:
    """Render the manual crime registration form for the active case."""
    st.markdown("#### Novo registro de ocorrência")

    if st.session_state.pop("_reset_crime_coordinates", False):
        st.session_state[LATITUDE_KEY] = DEFAULT_LATITUDE
        st.session_state[LONGITUDE_KEY] = DEFAULT_LONGITUDE
        st.success("Ocorrência cadastrada com sucesso.")
    else:
        st.session_state.setdefault(LATITUDE_KEY, DEFAULT_LATITUDE)
        st.session_state.setdefault(LONGITUDE_KEY, DEFAULT_LONGITUDE)

    address_cols = st.columns([4, 1])
    with address_cols[0]:
        address = st.text_input(
            "Endereço (opcional, para buscar coordenadas)",
            placeholder="Ex.: Av. Paulista, 1000, São Paulo",
        )
    with address_cols[1]:
        st.markdown("<div style='height: 1.85rem'></div>", unsafe_allow_html=True)
        if st.button("Buscar coordenadas", icon=":material/my_location:", width="stretch"):
            coordinate = geocode_address(address)
            if coordinate is None:
                st.warning("Endereço não encontrado.")
            else:
                st.session_state[LATITUDE_KEY] = coordinate.latitude
                st.session_state[LONGITUDE_KEY] = coordinate.longitude
                st.rerun()

    with st.form("crime_registration_form", clear_on_submit=True):
        form_cols = st.columns(3)

        with form_cols[0]:
            tipo_crime = st.text_input("Tipo de crime", placeholder="Ex.: Roubo")
            data = st.date_input("Data")
            hora = st.time_input("Hora")

        with form_cols[1]:
            latitude = st.number_input(
                "Latitude",
                min_value=-90.0,
                max_value=90.0,
                format="%.6f",
                key=LATITUDE_KEY,
            )
            longitude = st.number_input(
                "Longitude",
                min_value=-180.0,
                max_value=180.0,
                format="%.6f",
                key=LONGITUDE_KEY,
            )
            cidade = st.text_input("Cidade", placeholder="Ex.: São Paulo")

        with form_cols[2]:
            bairro = st.text_input("Bairro", placeholder="Ex.: Centro")
            modus_operandi = st.text_area("Modus operandi", height=90)
            observacoes = st.text_area("Observações", height=90)

        submitted = st.form_submit_button("Salvar ocorrência", icon=":material/save:", width="stretch")

    if not submitted:
        return

    try:
        if not tipo_crime.strip():
            raise ValueError("Informe o tipo de crime.")
        validate_coordinates(latitude, longitude)
        save_case_crime_record(
            caso_id,
            CrimeInput(
                tipo_crime=tipo_crime,
                data=data,
                hora=hora,
                latitude=latitude,
                longitude=longitude,
                cidade=cidade,
                bairro=bairro,
                modus_operandi=modus_operandi,
                observacoes=observacoes,
            ),
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    st.session_state["_reset_crime_coordinates"] = True
    st.rerun()


def render_import_section(caso_id: int) -> None:
    """Render the CSV/XLSX bulk-import section for the active case."""
    with st.expander("Importar ocorrências de CSV/XLSX"):
        uploaded_file = st.file_uploader("Arquivo", type=["csv", "xlsx"], key="import_uploader")
        if uploaded_file is None:
            return

        try:
            raw = read_uploaded_table(uploaded_file)
        except (ValueError, OSError) as exc:
            st.error(f"Não foi possível ler o arquivo: {exc}")
            return

        mapping_guess = guess_column_mapping(list(raw.columns))
        st.write("Confirme o mapeamento de colunas:")
        mapping: dict[str, str | None] = {}
        mapping_cols = st.columns(3)
        options = ["(nenhuma)"] + [str(column) for column in raw.columns]
        for index, field in enumerate(CANONICAL_IMPORT_FIELDS):
            with mapping_cols[index % 3]:
                default = mapping_guess.get(field)
                default_index = options.index(default) if default in options else 0
                choice = st.selectbox(field, options, index=default_index, key=f"import_map_{field}")
                mapping[field] = None if choice == "(nenhuma)" else choice

        missing_required = [field for field in REQUIRED_IMPORT_FIELDS if not mapping.get(field)]
        if missing_required:
            st.warning(f"Mapeie as colunas obrigatórias: {', '.join(sorted(missing_required))}")
            return

        mapped = apply_column_mapping(raw, mapping)
        st.write(f"Pré-visualização ({len(mapped)} linha(s) no arquivo):")
        st.dataframe(mapped.head(10), width="stretch", hide_index=True)

        if not st.button("Confirmar importação", key="confirm_import"):
            return

        try:
            prepared = prepare_crime_data(normalize_column_names(mapped))
        except ValueError as exc:
            st.error(str(exc))
            return

        ignored = len(mapped) - len(prepared)
        save_case_crime_records_bulk(caso_id, prepared)
        st.success(
            f"{len(prepared)} ocorrência(s) importada(s) com sucesso. "
            f"{ignored} ignorada(s) por dados inválidos ou incompletos."
        )


main()
