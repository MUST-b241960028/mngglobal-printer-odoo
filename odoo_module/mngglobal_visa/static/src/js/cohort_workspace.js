/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class CohortWorkspace extends Component {
    static template = "mngglobal_visa.CohortWorkspace";
    static props = { ...standardActionServiceProps };

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        const params = this.props.action.params || {};
        this.programId = params.program_id || false;
        this.state = useState({
            data: null,
            scope: params.scope || "all",
            cohortId: params.cohort_id || false,
            search: "",
            selectedId: false,
            draggingId: false,
            loading: true,
        });
        onWillStart(() => this.load());
    }

    get allCards() {
        return this.state.data
            ? this.state.data.columns.flatMap((column) => column.cards)
            : [];
    }

    get selectedLead() {
        return this.allCards.find((lead) => lead.id === this.state.selectedId) || false;
    }

    paymentLabel(status) {
        return {
            unpaid: "Төлөөгүй",
            partial: "Хэсэгчлэн төлсөн",
            paid: "Төлбөр төлсөн",
        }[status] || "Тодорхойгүй";
    }

    async load() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "mng.visa.application",
                "get_cohort_workspace_data",
                [this.programId, this.state.cohortId || false, this.state.scope, this.state.search]
            );
            this.state.data = data;
            if (!data.columns.some((column) => column.cards.some((lead) => lead.id === this.state.selectedId))) {
                this.state.selectedId = data.columns.flatMap((column) => column.cards)[0]?.id || false;
            }
        } finally {
            this.state.loading = false;
        }
    }

    async setScope(scope) {
        this.state.scope = scope;
        this.state.cohortId = false;
        await this.load();
    }

    async setCohort(cohortId) {
        this.state.scope = "cohort";
        this.state.cohortId = cohortId;
        await this.load();
    }

    selectLead(leadId) {
        this.state.selectedId = leadId;
    }

    onSearchInput(event) {
        this.state.search = event.target.value;
    }

    async onSearchSubmit(event) {
        event.preventDefault();
        await this.load();
    }

    async onDragStart(event, lead) {
        this.state.draggingId = lead.id;
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(lead.id));
    }

    async onDrop(event, column) {
        event.preventDefault();
        const leadId = Number(event.dataTransfer.getData("text/plain") || this.state.draggingId);
        this.state.draggingId = false;
        if (!leadId || !column.id) {
            return;
        }
        await this.orm.write("mng.visa.application", [leadId], { stage_id: column.id });
        await this.load();
    }

    allowDrop(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
    }

    openLead() {
        if (!this.selectedLead) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "mng.visa.application",
            res_id: this.selectedLead.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    newLead() {
        const context = {};
        if (this.programId) {
            context.default_program_type_id = this.programId;
        }
        if (this.state.scope === "cohort" && this.state.cohortId) {
            context.default_recruitment_period_id = this.state.cohortId;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "mng.visa.application",
            views: [[false, "form"]],
            target: "current",
            context,
        });
    }

    async executeLeadAction(method) {
        if (!this.selectedLead) {
            return;
        }
        const action = await this.orm.call("mng.visa.application", method, [[this.selectedLead.id]]);
        await this.actionService.doAction(action);
    }
}

registry.category("actions").add("mngglobal_visa.cohort_workspace", CohortWorkspace);
