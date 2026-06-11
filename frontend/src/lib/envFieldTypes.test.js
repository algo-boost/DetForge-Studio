import { describe, expect, it } from 'vitest';
import { formatFieldValueForEnv, readEnvValue } from './envFieldTypes';

describe('envFieldTypes', () => {
  it('readEnvValue reads uppercase keys', () => {
    expect(readEnvValue({ SAMPLE_SIZE: '300' }, 'sample_size')).toBe('300');
  });

  it('formatFieldValueForEnv stringifies scalars', () => {
    expect(formatFieldValueForEnv('text', 'hello')).toBe('hello');
    expect(formatFieldValueForEnv('number', 42)).toBe('42');
  });

  it('formatFieldValueForEnv joins multiselect arrays', () => {
    expect(formatFieldValueForEnv('multiselect', ['a', 'b'])).toBe('a,b');
  });
});
