import React from 'react';
import type {JSX} from 'react';
import Link from '@theme-original/DocSidebarItem/Link';
import type LinkType from '@theme/DocSidebarItem/Link';
import type {WrapperProps} from '@docusaurus/types';
import type {IconType} from 'react-icons';

import {
  LuBook, LuPackage, LuCircleCheck, LuShield, LuBlocks,
  LuLayers, LuBrain, LuMessageSquare, LuServer, LuSlidersHorizontal,
  LuCode, LuRss, LuExternalLink, LuArrowUpRight,
} from 'react-icons/lu';
import {SiGithub} from 'react-icons/si';

const ICON_MAP: Record<string, IconType> = {
  'lu-book':            LuBook,
  'lu-package':         LuPackage,
  'lu-check-circle':    LuCircleCheck,
  'lu-shield':          LuShield,
  'lu-blocks':          LuBlocks,
  'lu-layers':          LuLayers,
  'lu-brain':           LuBrain,
  'lu-message-square':  LuMessageSquare,
  'lu-server':          LuServer,
  'lu-sliders':         LuSlidersHorizontal,
  'lu-code':            LuCode,
  'lu-rss':             LuRss,
  'lu-external-link':   LuExternalLink,
  'lu-arrow-up-right':  LuArrowUpRight,
  'si-github':          SiGithub,
};

type Props = WrapperProps<typeof LinkType>;

export default function LinkWrapper(props: Props): JSX.Element {
  const {item} = props;
  const icon = item.customProps?.icon as string | undefined;
  const iconAfter = item.customProps?.iconAfter as string | undefined;

  if (!icon && !iconAfter) {
    return <Link {...props} />;
  }

  const IconComponent = icon ? ICON_MAP[icon] : undefined;
  const IconAfterComponent = iconAfter ? ICON_MAP[iconAfter] : undefined;

  const iconNode = IconComponent
    ? <IconComponent size={16} style={{flexShrink: 0, opacity: 0.65}} />
    : null;

  const iconAfterNode = IconAfterComponent
    ? <IconAfterComponent size={13} style={{flexShrink: 0, opacity: 0.45}} />
    : null;

  const modifiedItem = {
    ...item,
    label: (
      <span style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
        {iconNode}
        <span style={{flex: 1}}>{item.label}</span>
        {iconAfterNode}
      </span>
    ),
  };

  return <Link {...props} item={modifiedItem} />;
}
