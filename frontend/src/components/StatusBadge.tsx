import { LabelRecord } from '../types'
import {
  CheckCircle, AlertTriangle, HelpCircle, Clock, XCircle
} from 'lucide-react'

interface Props {
  status: LabelRecord['expiry_status'] | LabelRecord['review_status'] | string | null
  variant?: 'expiry' | 'review'
}

const EXPIRY_CFG = {
  expired:       { cls: 'badge-expired',  Icon: XCircle,       label: 'Expired'        },
  expiring_soon: { cls: 'badge-expiring', Icon: AlertTriangle,  label: 'Expiring Soon'  },
  ok:            { cls: 'badge-ok',       Icon: CheckCircle,    label: 'Valid'          },
  unknown:       { cls: 'badge-unknown',  Icon: HelpCircle,     label: 'Unknown'        },
}

const REVIEW_CFG = {
  confirmed:    { cls: 'badge-ok',     Icon: CheckCircle, label: 'Confirmed'    },
  needs_review: { cls: 'badge-review', Icon: Clock,       label: 'Needs Review' },
}

export default function StatusBadge({ status, variant = 'expiry' }: Props) {
  const cfg =
    variant === 'review'
      ? (REVIEW_CFG as any)[status as string]
      : (EXPIRY_CFG as any)[status as string]

  if (!cfg) return <span className="badge-unknown">—</span>
  const { cls, Icon, label } = cfg
  return (
    <span className={cls}>
      <Icon size={11} />
      {label}
    </span>
  )
}
