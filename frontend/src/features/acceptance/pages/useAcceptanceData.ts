import { useEffect, useMemo, useState } from "react";
import {
  getProjectContext,
  getRequestDailyReport,
  listParticipantProfiles,
  listRecords,
  listRequests,
  listWorkItems,
} from "../lib/api";
import { errorMessage } from "./acceptancePageModel";
import type {
  AcceptanceRecord,
  AcceptanceRequest,
  LinkedDailyReport,
  ParticipantProfile,
  ProjectContext,
  WorkItemSummary,
} from "../types";

type Options = {
  projectId: string;
  onProjectChange: () => void;
  setError: (value: string | null) => void;
};

export function useAcceptanceData({
  projectId,
  onProjectChange,
  setError,
}: Options) {
  const [requests, setRequests] = useState<AcceptanceRequest[]>([]);
  const [records, setRecords] = useState<AcceptanceRecord[]>([]);
  const [profiles, setProfiles] = useState<ParticipantProfile[]>([]);
  const [workItems, setWorkItems] = useState<WorkItemSummary[]>([]);
  const [projectContext, setProjectContext] = useState<ProjectContext | null>(null);
  const [reportLinks, setReportLinks] = useState<
    Record<string, LinkedDailyReport | null>
  >({});

  async function refresh() {
    const [requestList, recordList] = await Promise.all([
      listRequests(projectId),
      listRecords(projectId),
    ]);
    setRequests(requestList);
    setRecords(recordList);
    return { requestList, recordList };
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [requestList, recordList, profileList, project] = await Promise.all([
          listRequests(projectId),
          listRecords(projectId),
          listParticipantProfiles(projectId),
          getProjectContext(projectId).catch(() => null),
        ]);
        if (!active) return;
        setRequests(requestList);
        setRecords(recordList);
        setProfiles(profileList);
        setProjectContext(project);
      } catch (cause) {
        if (active) setError(errorMessage(cause));
      }
    })();
    onProjectChange();
    setProjectContext(null);
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    let active = true;
    setWorkItems([]);
    // Keep this separate from the main Promise.all: a failing work-item
    // catalog must not block PYC/BBNT loading.
    listWorkItems(projectId)
      .then((items) => {
        if (active) setWorkItems(items);
      })
      .catch(() => {
        if (active) setWorkItems([]);
      });
    return () => {
      active = false;
    };
  }, [projectId]);

  useEffect(() => {
    let active = true;
    const linked = requests.filter((request) => request.daily_report_id);
    if (linked.length === 0) {
      setReportLinks({});
      return;
    }
    Promise.all(
      linked.map(async (request) => {
        try {
          const report = await getRequestDailyReport(projectId, request.id);
          return [request.id, report] as const;
        } catch {
          return [request.id, null] as const;
        }
      }),
    ).then((entries) => {
      if (active) setReportLinks(Object.fromEntries(entries));
    });
    return () => {
      active = false;
    };
  }, [projectId, requests]);

  const recordsByRequest = useMemo(() => {
    const map = new Map<string, AcceptanceRecord>();
    for (const record of records) {
      if (!map.has(record.request_id)) map.set(record.request_id, record);
    }
    return map;
  }, [records]);

  function recordFor(requestId: string): AcceptanceRecord | undefined {
    return recordsByRequest.get(requestId);
  }

  return {
    requests,
    records,
    profiles,
    workItems,
    projectContext,
    reportLinks,
    refresh,
    recordFor,
    setRecords,
    setProfiles,
  };
}
