import QueryComposeModule from './modules/QueryComposeModule';
import PredictComposeModule from './modules/PredictComposeModule';
import CurationCreateComposeModule from './modules/CurationCreateComposeModule';
import {
  CurationArchiveComposeModule,
  CurationExportComposeModule,
  CurationImportComposeModule,
  GateHumanComposeModule,
  NotifyComposeModule,
  SchemaFallbackModule,
} from './modules/CurationStepComposeModules';

/** @typedef {import('react').ComponentType<{ value: object, onChange: Function, bindHints?: object[], models?: object[], paramsSchema?: object, lockDataSource?: string|null }>} ComposeModuleComponent */

/** @type {Record<string, ComposeModuleComponent>} */
export const COMPOSE_MODULE_PANELS = {
  query: QueryComposeModule,
  query_predict: (props) => (
    <QueryComposeModule {...props} lockDataSource="predict_result" />
  ),
  predict: PredictComposeModule,
  curation_create: CurationCreateComposeModule,
  curation_export: CurationExportComposeModule,
  gate_human: GateHumanComposeModule,
  curation_import: CurationImportComposeModule,
  curation_archive: CurationArchiveComposeModule,
  notify: NotifyComposeModule,
};

export function ComposeModuleBody({
  moduleId,
  paramsSchema,
  value,
  onChange,
  bindHints = [],
  models = [],
}) {
  const Panel = COMPOSE_MODULE_PANELS[moduleId];
  if (Panel) {
    return (
      <Panel
        value={value}
        onChange={onChange}
        bindHints={bindHints}
        models={models}
        paramsSchema={paramsSchema}
      />
    );
  }
  return (
    <SchemaFallbackModule
      paramsSchema={paramsSchema}
      value={value}
      onChange={onChange}
      models={models}
    />
  );
}
