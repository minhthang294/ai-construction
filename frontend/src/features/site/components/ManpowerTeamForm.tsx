import { useState } from "react";
import type { ManpowerEntry, ManpowerPreset, Organization } from "../types";
import { summarizeManpower } from "../lib/manpower";
import {
  contactNamesForRole,
  normalizeManpowerCount,
  normalizePersonName,
  splitManpowerTeam,
  teamToManpowerEntries,
  type ManpowerRole,
} from "../lib/manpowerTeam";
import ManpowerTable from "./ManpowerTable";

type Props = {
  entries: ManpowerEntry[];
  onChange: (entries: ManpowerEntry[]) => void;
  contacts?: ManpowerPreset[];
  organizations?: Organization[];
};

const NUMERIC_ROLES: Array<{
  key: Extract<ManpowerRole, "lai_xe" | "bao_ve" | "cong_nhan">;
  label: string;
}> = [
  { key: "lai_xe", label: "Lái xe" },
  { key: "bao_ve", label: "Bảo vệ" },
  { key: "cong_nhan", label: "Công nhân" },
];

export default function ManpowerTeamForm({
  entries,
  onChange,
  contacts = [],
  organizations = [],
}: Props) {
  const { team, legacy } = splitManpowerTeam(entries);
  const [newEngineer, setNewEngineer] = useState("");
  const chiefNames = contactNamesForRole(contacts, "chi_huy_truong");
  const engineerNames = contactNamesForRole(contacts, "ky_thuat");
  const summary = summarizeManpower(entries);

  function commit(
    patch: Partial<typeof team>,
    nextLegacy: ManpowerEntry[] = legacy,
  ) {
    onChange(teamToManpowerEntries({ ...team, ...patch }, nextLegacy));
  }

  function updateEngineer(index: number, value: string) {
    const next = team.ky_thuat.map((name, idx) => (idx === index ? value : name));
    commit({ ky_thuat: next });
  }

  function addEngineer() {
    const name = normalizePersonName(newEngineer) ?? "";
    if (!name) return;
    const exists = team.ky_thuat.some(
      (item) => item.toLocaleLowerCase("vi") === name.toLocaleLowerCase("vi"),
    );
    if (!exists) {
      commit({ ky_thuat: [...team.ky_thuat, name] });
    }
    setNewEngineer("");
  }

  function removeEngineer(index: number) {
    commit({ ky_thuat: team.ky_thuat.filter((_, idx) => idx !== index) });
  }

  return (
    <section className="space-y-3 rounded-xl bg-white p-3 shadow-sm">
      <div>
        <h3 className="text-lg font-semibold">Nhân lực</h3>
        <p className="text-xs text-gray-500">
          Một Chỉ huy trưởng, nhiều Kỹ thuật (nhập tên). Lái xe, Bảo vệ, Công nhân
          là số người, mặc định 0. Tên Chỉ huy trưởng/Kỹ thuật được lưu vào danh
          bạ nhân lực khi lưu báo cáo.
        </p>
      </div>

      <div className="space-y-2">
        <label
          className="block text-sm font-medium text-gray-700"
          htmlFor="manpower-chief"
        >
          Chỉ huy trưởng
        </label>
        <input
          id="manpower-chief"
          className="min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
          list="manpower-chief-contacts"
          placeholder="Họ tên Chỉ huy trưởng"
          value={team.chi_huy_truong ?? ""}
          onChange={(event) =>
            // Keep raw text (including a just-typed trailing space) in the draft.
            commit({ chi_huy_truong: event.target.value || null })
          }
          onBlur={(event) =>
            commit({ chi_huy_truong: normalizePersonName(event.target.value) })
          }
        />
        <datalist id="manpower-chief-contacts">
          {chiefNames.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-gray-700">Kỹ thuật</p>
        <datalist id="manpower-engineer-contacts">
          {engineerNames.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
        {team.ky_thuat.length === 0 && (
          <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-500">
            Chưa có Kỹ thuật. Nhập tên bên dưới để thêm.
          </p>
        )}
        {team.ky_thuat.map((name, index) => (
          <div key={index} className="flex items-center gap-2">
            <input
              className="min-h-11 min-w-0 flex-1 rounded-lg border border-gray-300 px-3 text-base"
              list="manpower-engineer-contacts"
              placeholder={`Họ tên Kỹ thuật ${index + 1}`}
              value={name}
              onChange={(event) => updateEngineer(index, event.target.value)}
              onBlur={(event) =>
                updateEngineer(index, normalizePersonName(event.target.value) ?? "")
              }
            />
            <button
              type="button"
              className="min-h-11 min-w-11 shrink-0 px-2 text-sm text-red-600"
              aria-label={`Xoá Kỹ thuật ${index + 1}`}
              onClick={() => removeEngineer(index)}
            >
              Xoá
            </button>
          </div>
        ))}
        <div className="flex items-center gap-2">
          <input
            className="min-h-11 min-w-0 flex-1 rounded-lg border border-dashed border-gray-300 px-3 text-base"
            list="manpower-engineer-contacts"
            placeholder="Thêm họ tên Kỹ thuật"
            value={newEngineer}
            onChange={(event) => setNewEngineer(event.target.value)}
            onBlur={(event) =>
              setNewEngineer(normalizePersonName(event.target.value) ?? "")
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addEngineer();
              }
            }}
          />
          <button
            type="button"
            className="min-h-11 min-w-11 shrink-0 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white"
            onClick={addEngineer}
          >
            Thêm
          </button>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        {NUMERIC_ROLES.map((role) => (
          <label key={role.key} className="block text-sm text-gray-700">
            {role.label}
            <input
              type="number"
              inputMode="numeric"
              min={0}
              step={1}
              className="mt-1 min-h-11 w-full rounded-lg border border-gray-300 px-3 text-base"
              value={team[role.key]}
              onChange={(event) =>
                commit({ [role.key]: normalizeManpowerCount(event.target.value) })
              }
            />
          </label>
        ))}
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-blue-50 px-3 py-1 text-blue-800">
          Tổng đã biết: <b>{summary.knownTotal}</b>
        </span>
        {summary.unknownGroups.length > 0 && (
          <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-800">
            Chưa rõ: {summary.unknownGroups.join(", ")}
          </span>
        )}
        {summary.zeroGroups.length > 0 && (
          <span className="rounded-full bg-gray-100 px-3 py-1 text-gray-700">
            0 người: {summary.zeroGroups.join(", ")}
          </span>
        )}
      </div>

      <details className="rounded-lg border border-gray-200 p-2">
        <summary className="min-h-11 cursor-pointer py-2 text-sm font-medium text-gray-700">
          Nhân lực khác / dữ liệu cũ ({legacy.length})
        </summary>
        <p className="mt-1 text-xs text-gray-500">
          Các nhóm không thuộc Chỉ huy trưởng/Kỹ thuật/Lái xe/Bảo vệ/Công nhân
          được giữ nguyên để không mất dữ liệu báo cáo cũ.
        </p>
        <div className="mt-2">
          <ManpowerTable
            entries={legacy}
            organizations={organizations}
            onChange={(nextLegacy) =>
              onChange(teamToManpowerEntries(team, nextLegacy))
            }
          />
        </div>
      </details>
    </section>
  );
}
