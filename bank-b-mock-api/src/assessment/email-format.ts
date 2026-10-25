import { domainToASCII } from "node:url";
import { Format } from "typebox/format";

const MAX_EMAIL_LENGTH = 254;
const MAX_DOMAIN_LENGTH = 253;
const MAX_LABEL_LENGTH = 63;

function findUnquotedAt(value: string): number {
  let quoted = false;
  let escaped = false;
  let separator = -1;

  for (let index = 0; index < value.length; index += 1) {
    const character = value[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (quoted && character === "\\") {
      escaped = true;
      continue;
    }
    if (character === '"') {
      quoted = !quoted;
    } else if (!quoted && character === "@") {
      if (separator !== -1) return -1;
      separator = index;
    }
  }

  return quoted || escaped ? -1 : separator;
}

function hasInvalidDomainSyntax(domain: string): boolean {
  return [...domain].some(
    (character) =>
      character === "/" ||
      character === "?" ||
      character === "#" ||
      character === "\\" ||
      character === "%" ||
      /\s/u.test(character) ||
      character.codePointAt(0)! <= 0x1f ||
      character.codePointAt(0)! === 0x7f,
  );
}

export function isInternationalizedEmail(value: string): boolean {
  if (value.length > MAX_EMAIL_LENGTH) return false;

  const separator = findUnquotedAt(value);
  if (separator <= 0 || separator === value.length - 1) return false;

  const localPart = value.slice(0, separator);
  const domain = value.slice(separator + 1);
  if (hasInvalidDomainSyntax(domain)) return false;

  let asciiDomain: string;
  try {
    asciiDomain = domainToASCII(domain);
  } catch {
    return false;
  }

  if (
    asciiDomain.length === 0 ||
    asciiDomain.length > MAX_DOMAIN_LENGTH ||
    asciiDomain.split(".").some(
      (label) => label.length === 0 || label.length > MAX_LABEL_LENGTH,
    )
  ) {
    return false;
  }

  return Format.IsIdnEmail(`${localPart}@${asciiDomain}`);
}
