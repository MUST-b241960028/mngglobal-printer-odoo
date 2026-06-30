/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const MODEL_META = {
    "mng.daily.report": {
        title: _t("Өдрийн тайлан"),
        emptyAction: _t("Юу хийсэн?"),
        themeClass: "o_mng_matrix--report",
    },
    "mng.daily.plan": {
        title: _t("Өдрийн төлөвлөгөө"),
        emptyAction: _t("Юу хийхээр төлөвлөж байна?"),
        themeClass: "o_mng_matrix--plan",
    },
};

export class MonthlyMatrix extends Component {
    static template = "mngglobal_logs.MonthlyMatrix";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.ui = useService("ui"); // reactive { isSmall, size } — same one used by Odoo's own responsive views

        const params = this.props.action?.params || {};
        const today = new Date();
        const model = params.model || "mng.daily.report";

        this.state = useState({
            model,
            meta: MODEL_META[model] || MODEL_META["mng.daily.report"],
            year: today.getFullYear(),
            month: today.getMonth() + 1, // JS 0-based, Python 1-based
            year_input: today.getFullYear(),
            month_input: today.getMonth() + 1,
            data: null,
            loading: true,
            statsOpen: false, // collapsed by default on mobile
        });

        onWillStart(async () => {
            await this.loadMatrix();
        });
    }

    toggleStats() {
        this.state.statsOpen = !this.state.statsOpen;
    }

    async loadMatrix() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                this.state.model,
                "get_monthly_matrix",
                [this.state.year, this.state.month],
            );
        } catch (e) {
            this.notification.add(_t("Матрицыг ачаалж чадсангүй."), { type: "danger" });
            this.state.data = null;
        }
        this.state.loading = false;
    }

    // ────── Month navigation ──────

    async prevMonth() {
        if (this.state.month === 1) {
            this.state.month = 12;
            this.state.year -= 1;
        } else {
            this.state.month -= 1;
        }
        this.state.year_input = this.state.year;
        this.state.month_input = this.state.month;
        await this.loadMatrix();
    }

    async nextMonth() {
        if (this.state.month === 12) {
            this.state.month = 1;
            this.state.year += 1;
        } else {
            this.state.month += 1;
        }
        this.state.year_input = this.state.year;
        this.state.month_input = this.state.month;
        await this.loadMatrix();
    }

    async goToday() {
        const t = new Date();
        this.state.year = t.getFullYear();
        this.state.month = t.getMonth() + 1;
        this.state.year_input = this.state.year;
        this.state.month_input = this.state.month;
        await this.loadMatrix();
    }

    async toggleModel() {
        const other = this.state.model === "mng.daily.report"
            ? "mng.daily.plan"
            : "mng.daily.report";
        this.state.model = other;
        this.state.meta = MODEL_META[other];
        await this.loadMatrix();
    }

    async openListView() {
        // open the standard list/form/calendar/pivot action for power users
        const actionRef = this.state.model === "mng.daily.report"
            ? "mngglobal_logs.mng_daily_report_action"
            : "mngglobal_logs.mng_daily_plan_action";
        await this.actionService.doAction(actionRef);
    }

    // ────── Cell helpers ──────

    getEntry(iso, userId) {
        return this.state.data?.entries[`${iso}_${userId}`] || null;
    }

    // Sidebar stats sorted by count desc, then name asc (most active on top)
    get sortedStatsUsers() {
        if (!this.state.data) return [];
        const stats = this.state.data.stats || {};
        return [...this.state.data.users].sort((a, b) => {
            const diff = (stats[b.id] || 0) - (stats[a.id] || 0);
            if (diff !== 0) return diff;
            return (a.name || "").localeCompare(b.name || "");
        });
    }

    canCreateHere(userId) {
        if (!this.state.data) return false;
        return this.state.data.is_manager || userId === this.state.data.current_uid;
    }

    cellClass(date, user) {
        const entry = this.getEntry(date.iso, user.id);
        const classes = ["o_mng_matrix__cell"];
        if (date.is_weekend) classes.push("o_mng_matrix__cell--weekend");
        if (date.is_today) classes.push("o_mng_matrix__cell--today");
        if (entry) {
            classes.push("o_mng_matrix__cell--filled");
            if (entry.can_edit) classes.push("o_mng_matrix__cell--editable");
        } else if (this.canCreateHere(user.id)) {
            classes.push("o_mng_matrix__cell--creatable");
        } else {
            classes.push("o_mng_matrix__cell--readonly");
        }
        if (user.id === this.state.data?.current_uid) {
            classes.push("o_mng_matrix__cell--mine");
        }
        return classes.join(" ");
    }

    rowClass(date) {
        const classes = ["o_mng_matrix__row"];
        if (date.is_weekend) classes.push("o_mng_matrix__row--weekend");
        if (date.is_today) classes.push("o_mng_matrix__row--today");
        return classes.join(" ");
    }

    // ────── Click handlers ──────

    async onCellClick(date, user) {
        const entry = this.getEntry(date.iso, user.id);
        if (entry) {
            // Open existing entry in a modal form
            await this.actionService.doAction(
                {
                    type: "ir.actions.act_window",
                    res_model: this.state.model,
                    res_id: entry.id,
                    views: [[false, "form"]],
                    target: "new",
                },
                {
                    onClose: () => this.loadMatrix(),
                },
            );
        } else if (this.canCreateHere(user.id)) {
            // Create new entry pre-filled with this (date, user)
            await this.actionService.doAction(
                {
                    type: "ir.actions.act_window",
                    res_model: this.state.model,
                    views: [[false, "form"]],
                    target: "new",
                    context: {
                        default_log_date: date.iso,
                        default_user_id: user.id,
                    },
                },
                {
                    onClose: () => this.loadMatrix(),
                },
            );
        }
        // else: empty, others' cell → no-op (visually shown as —)
    }
}

registry.category("actions").add("mngglobal_logs.monthly_matrix", MonthlyMatrix);
